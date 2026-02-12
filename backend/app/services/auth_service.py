"""
Authentication service containing business logic for user registration and authentication.
"""

import logging
from datetime import timedelta
from typing import NamedTuple, Optional
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_csrf_token,
    create_refresh_token,
    get_password_hash,
    hash_refresh_token,
    verify_password,
)
from app.db.timezone import utcnow
from app.models.auth_session import RefreshTokenSession
from app.models.user import User
from app.schemas.auth import UserRegister, UserLogin

logger = logging.getLogger(__name__)


class IssuedAuthTokens(NamedTuple):
    access_token: str
    refresh_token: str
    csrf_token: str


class AuthService:
    """
    Service class for authentication operations.
    """
    
    @staticmethod
    def register_user(db: Session, user_data: UserRegister) -> User:
        """
        Register a new user.
        
        Args:
            db: Database session
            user_data: User registration data
            
        Returns:
            Created User object
            
        Raises:
            HTTPException: If email already exists or registration fails
        """
        try:
            # Check if email already exists
            existing_user = db.query(User).filter(User.email == user_data.email).first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            
            # Hash password
            password_hash = get_password_hash(user_data.password)
            
            # Create user
            new_user = User(
                email=user_data.email,
                name=user_data.name,
                phone=user_data.phone,
                password_hash=password_hash,
                role="advisor"
            )
            
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            
            logger.info(f"User registered successfully: {new_user.email}")
            return new_user
            
        except HTTPException:
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Registration failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed"
            )
    
    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
        """
        Authenticate a user by email and password.
        
        Args:
            db: Database session
            email: User's email address
            password: User's plain text password
            
        Returns:
            User object if authentication successful, None otherwise
        """
        try:
            # Get user by email
            user = db.query(User).filter(User.email == email).first()
            
            if not user:
                logger.warning(f"Authentication failed: User not found - {email}")
                return None
            
            # Verify password
            if not verify_password(password, user.password_hash):
                logger.warning(f"Authentication failed: Invalid password - {email}")
                return None
            
            logger.info(f"User authenticated successfully: {email}")
            return user
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None

    @staticmethod
    def _authenticate_credentials(db: Session, credentials: UserLogin) -> User:
        user = db.query(User).filter(User.email == credentials.email).first()
        if not user or not verify_password(credentials.password, user.password_hash):
            logger.warning(f"Login failed: Invalid credentials for {credentials.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    @staticmethod
    def _build_access_token(user: User, *, family_id: str) -> str:
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        return create_access_token(
            data={
                "sub": user.email,
                "uid": user.id,
                "fid": family_id,
                "typ": "access",
            },
            expires_delta=access_token_expires,
        )

    @staticmethod
    def _issue_refresh_session(
        db: Session,
        *,
        user: User,
        family_id: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> str:
        refresh_token = create_refresh_token()
        session = RefreshTokenSession(
            user_id=user.id,
            family_id=family_id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=(user_agent or "")[:255] or None,
            ip_address=(ip_address or "")[:45] or None,
        )
        db.add(session)
        return refresh_token

    @staticmethod
    def _revoke_family(db: Session, *, user_id: int, family_id: str, reason: str) -> None:
        now = utcnow()
        sessions = (
            db.query(RefreshTokenSession)
            .filter(
                RefreshTokenSession.user_id == user_id,
                RefreshTokenSession.family_id == family_id,
            )
            .all()
        )
        for session in sessions:
            if session.revoked_at is None:
                session.revoked_at = now
                session.revoked_reason = reason

    @staticmethod
    def login_and_issue_tokens(
        db: Session,
        credentials: UserLogin,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> IssuedAuthTokens:
        """
        Authenticate user and issue access/refresh/CSRF tokens.
        """
        try:
            user = AuthService._authenticate_credentials(db, credentials)
            family_id = str(uuid4())
            access_token = AuthService._build_access_token(
                user,
                family_id=family_id,
            )
            refresh_token = AuthService._issue_refresh_session(
                db,
                user=user,
                family_id=family_id,
                user_agent=user_agent,
                ip_address=ip_address,
            )
            csrf_token = create_csrf_token()
            db.commit()
            logger.info(f"Login successful for email: {credentials.email}")
            return IssuedAuthTokens(
                access_token=access_token,
                refresh_token=refresh_token,
                csrf_token=csrf_token,
            )
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Login error for {credentials.email}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during login",
            )

    @staticmethod
    def refresh_tokens(
        db: Session,
        *,
        refresh_token: str,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> IssuedAuthTokens:
        token_hash = hash_refresh_token(refresh_token)
        now = utcnow()
        try:
            session = (
                db.query(RefreshTokenSession)
                .filter(RefreshTokenSession.token_hash == token_hash)
                .first()
            )
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token",
                )

            user = db.query(User).filter(User.id == session.user_id).first()
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token",
                )

            if session.revoked_at is not None:
                AuthService._revoke_family(
                    db,
                    user_id=session.user_id,
                    family_id=session.family_id,
                    reason="reused_token_detected",
                )
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token reuse detected",
                )

            if session.expires_at <= now:
                session.revoked_at = now
                session.revoked_reason = "expired"
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token expired",
                )

            session.last_used_at = now
            session.revoked_at = now
            session.revoked_reason = "rotated"

            access_token = AuthService._build_access_token(
                user,
                family_id=session.family_id,
            )
            next_refresh_token = AuthService._issue_refresh_session(
                db,
                user=user,
                family_id=session.family_id,
                user_agent=user_agent,
                ip_address=ip_address,
            )
            csrf_token = create_csrf_token()
            db.commit()
            return IssuedAuthTokens(
                access_token=access_token,
                refresh_token=next_refresh_token,
                csrf_token=csrf_token,
            )
        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Refresh token error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during token refresh",
            )

    @staticmethod
    def logout_user(db: Session, *, refresh_token: str | None) -> None:
        if not refresh_token:
            return

        token_hash = hash_refresh_token(refresh_token)
        now = utcnow()
        try:
            session = (
                db.query(RefreshTokenSession)
                .filter(RefreshTokenSession.token_hash == token_hash)
                .first()
            )
            if not session:
                return

            AuthService._revoke_family(
                db,
                user_id=session.user_id,
                family_id=session.family_id,
                reason="logout",
            )
            session.last_used_at = now
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Logout revocation failed")
