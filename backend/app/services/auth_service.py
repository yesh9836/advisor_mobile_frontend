"""
Authentication service containing business logic for user registration and authentication.
"""

import logging
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import NamedTuple, Optional
from urllib.parse import quote_plus
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_csrf_token,
    create_password_reset_token,
    create_refresh_token,
    get_password_hash,
    hash_password_reset_token,
    hash_refresh_token,
    verify_password,
)
from app.db.timezone import utcnow
from app.models.auth_session import RefreshTokenSession
from app.models.notification import NotificationOutbox
from app.models.password_reset import PasswordResetRequestAttempt, PasswordResetToken
from app.models.user import User
from app.schemas.auth import PasswordResetConfirm, PasswordResetRequest, UserRegister, UserLogin
from app.services.notification_template_service import NotificationTemplateService

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
    def _normalize_email(email: str) -> str:
        return (email or "").strip().lower()

    @staticmethod
    def _find_user_by_email(db: Session, email: str) -> User | None:
        normalized_email = AuthService._normalize_email(email)
        if not normalized_email:
            return None

        # Fast-path for canonicalized rows, then fall back for legacy mixed-case records.
        user = db.query(User).filter(User.email == normalized_email).first()
        if user is not None:
            return user
        return db.query(User).filter(func.lower(User.email) == normalized_email).first()
    
    @staticmethod
    def _is_duplicate_email_integrity_error(exc: IntegrityError) -> bool:
        details = " ".join(
            [
                str(exc).lower(),
                str(getattr(exc, "orig", "")).lower(),
                str(getattr(exc, "statement", "")).lower(),
                str(getattr(exc, "params", "")).lower(),
            ]
        )
        has_duplicate_marker = any(
            marker in details
            for marker in (
                "duplicate",
                "duplicate entry",
                "duplicate key value",
                "unique constraint",
                "unique constraint failed",
            )
        )
        has_email_marker = "email" in details
        return has_duplicate_marker and has_email_marker

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
            normalized_email = AuthService._normalize_email(str(user_data.email))

            # Check if email already exists
            existing_user = AuthService._find_user_by_email(db, normalized_email)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
            
            # Hash password
            password_hash = get_password_hash(user_data.password)
            
            # Create user
            new_user = User(
                email=normalized_email,
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
        except IntegrityError as exc:
            db.rollback()
            if AuthService._is_duplicate_email_integrity_error(exc):
                logger.info("Registration rejected duplicate email at commit: %s", normalized_email)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                ) from exc
            logger.exception("Registration failed with integrity error")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Registration failed",
            ) from exc
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
            normalized_email = AuthService._normalize_email(email)

            # Get user by email
            user = AuthService._find_user_by_email(db, normalized_email)
            
            if not user:
                logger.warning(f"Authentication failed: User not found - {normalized_email}")
                return None
            
            # Verify password
            if not verify_password(password, user.password_hash):
                logger.warning(f"Authentication failed: Invalid password - {normalized_email}")
                return None
            
            logger.info(f"User authenticated successfully: {normalized_email}")
            return user
            
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return None

    @staticmethod
    def _authenticate_credentials(db: Session, credentials: UserLogin) -> User:
        normalized_email = AuthService._normalize_email(str(credentials.email))
        user = AuthService._find_user_by_email(db, normalized_email)
        if not user or not verify_password(credentials.password, user.password_hash):
            logger.warning(f"Login failed: Invalid credentials for {normalized_email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            logger.warning("Login blocked for inactive account: %s", normalized_email)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user account",
            )
        # Opportunistically canonicalize legacy mixed-case rows on successful authentication.
        if user.email != normalized_email:
            user.email = normalized_email
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
    def revoke_all_user_refresh_sessions(db: Session, *, user_id: int, reason: str) -> None:
        now = utcnow()
        sessions = (
            db.query(RefreshTokenSession)
            .filter(
                RefreshTokenSession.user_id == user_id,
                RefreshTokenSession.revoked_at.is_(None),
            )
            .all()
        )
        for session in sessions:
            session.revoked_at = now
            session.revoked_reason = reason

    @staticmethod
    def _get_refresh_session_for_rotation(
        db: Session,
        *,
        token_hash: str,
    ) -> RefreshTokenSession | None:
        return (
            db.query(RefreshTokenSession)
            .filter(RefreshTokenSession.token_hash == token_hash)
            .with_for_update()
            .first()
        )

    @staticmethod
    def _consume_refresh_session(
        db: Session,
        *,
        session_id: int,
        consumed_at: datetime,
        reason: str,
    ) -> bool:
        updated_rows = (
            db.query(RefreshTokenSession)
            .filter(
                RefreshTokenSession.id == session_id,
                RefreshTokenSession.revoked_at.is_(None),
            )
            .update(
                {
                    RefreshTokenSession.last_used_at: consumed_at,
                    RefreshTokenSession.revoked_at: consumed_at,
                    RefreshTokenSession.revoked_reason: reason,
                },
                synchronize_session=False,
            )
        )
        return updated_rows == 1

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
            session = AuthService._get_refresh_session_for_rotation(
                db,
                token_hash=token_hash,
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
            if not user.is_active:
                AuthService._revoke_family(
                    db,
                    user_id=session.user_id,
                    family_id=session.family_id,
                    reason="inactive_user",
                )
                db.commit()
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
                consumed = AuthService._consume_refresh_session(
                    db,
                    session_id=session.id,
                    consumed_at=now,
                    reason="expired",
                )
                if not consumed:
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
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Refresh token expired",
                )

            consumed = AuthService._consume_refresh_session(
                db,
                session_id=session.id,
                consumed_at=now,
                reason="rotated",
            )
            if not consumed:
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

    @staticmethod
    def _build_password_reset_url(token: str) -> str:
        frontend_base_url = settings.FRONTEND_URL.rstrip("/")
        return f"{frontend_base_url}/reset-password?token={quote_plus(token)}"

    @staticmethod
    def _is_password_reset_rate_limited(
        db: Session,
        *,
        subject_hash: str,
        now: datetime,
    ) -> tuple[bool, int]:
        window_start = now - timedelta(hours=1)
        recent_requests_query = (
            db.query(PasswordResetRequestAttempt)
            .filter(
                PasswordResetRequestAttempt.subject_hash == subject_hash,
                PasswordResetRequestAttempt.created_at >= window_start,
            )
        )
        issued_count = recent_requests_query.count()
        if issued_count < settings.PASSWORD_RESET_REQUESTS_PER_HOUR:
            return False, 0

        oldest_request = recent_requests_query.order_by(PasswordResetRequestAttempt.created_at.asc()).first()
        if oldest_request is None:
            return False, 0
        retry_after_seconds = max(
            1,
            int(((oldest_request.created_at + timedelta(hours=1)) - now).total_seconds()),
        )
        return True, retry_after_seconds

    @staticmethod
    def _password_reset_rate_limit_subject_hash(email: str) -> str:
        normalized_email = AuthService._normalize_email(email)
        return hmac.new(
            settings.SECRET_KEY.encode("utf-8"),
            normalized_email.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def _build_password_reset_email_idempotency_key(
        *,
        user_id: int,
        token_hash: str,
    ) -> str:
        return f"password_reset_requested:email:u{int(user_id)}:{token_hash}"

    @staticmethod
    def _enqueue_password_reset_email_outbox(
        db: Session,
        *,
        user: User,
        reset_url: str,
        token_hash: str,
        now: datetime,
    ) -> None:
        template = NotificationTemplateService.render_password_reset_email(
            app_name=settings.APP_NAME,
            recipient_name=user.name,
            reset_url=reset_url,
            expires_minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES,
        )
        db.add(
            NotificationOutbox(
                user_id=user.id,
                lead_id=None,
                purchase_id=None,
                channel="email",
                event_type="password_reset_requested",
                recipient=user.email,
                subject=template.subject,
                message_body=template.text_body,
                payload={
                    "html_body": template.html_body,
                    "source_event": "password_reset_request",
                },
                idempotency_key=AuthService._build_password_reset_email_idempotency_key(
                    user_id=user.id,
                    token_hash=token_hash,
                ),
                status="pending",
                attempt_count=0,
                max_attempts=settings.NOTIFICATION_OUTBOX_MAX_ATTEMPTS,
                next_retry_at=now,
            )
        )

    @staticmethod
    def _invalidate_active_password_reset_tokens(
        db: Session,
        *,
        user_id: int,
        now: datetime,
        exclude_token_hash: str | None = None,
    ) -> int:
        query = db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user_id,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        if exclude_token_hash:
            query = query.filter(PasswordResetToken.token_hash != exclude_token_hash)
        updated_rows = query.update(
            {PasswordResetToken.used_at: now},
            synchronize_session=False,
        )
        return int(updated_rows or 0)

    @staticmethod
    def request_password_reset(
        db: Session,
        payload: PasswordResetRequest,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        """
        Best-effort password reset request flow.

        This method intentionally avoids raising user-facing errors so callers can
        always return a generic response that does not leak account existence.
        """
        try:
            now = utcnow()
            normalized_email = AuthService._normalize_email(str(payload.email))
            subject_hash = AuthService._password_reset_rate_limit_subject_hash(normalized_email)
            is_rate_limited, retry_after_seconds = AuthService._is_password_reset_rate_limited(
                db,
                subject_hash=subject_hash,
                now=now,
            )
            if is_rate_limited:
                logger.info("Password reset request rate-limited for subject hash")
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        "Too many password reset requests. Please wait before requesting another reset email."
                    ),
                    headers={"Retry-After": str(retry_after_seconds)},
                )

            db.add(PasswordResetRequestAttempt(subject_hash=subject_hash))
            user = AuthService._find_user_by_email(db, normalized_email)
            if not user or not user.is_active:
                db.commit()
                return
            if user.email != normalized_email:
                user.email = normalized_email
            AuthService._invalidate_active_password_reset_tokens(
                db,
                user_id=user.id,
                now=now,
            )

            raw_token = create_password_reset_token()
            token_hash = hash_password_reset_token(raw_token)
            token_record = PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=now + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
                requested_user_agent=(user_agent or "")[:255] or None,
                requested_ip=(ip_address or "")[:45] or None,
            )
            db.add(token_record)

            reset_url = AuthService._build_password_reset_url(raw_token)
            AuthService._enqueue_password_reset_email_outbox(
                db,
                user=user,
                reset_url=reset_url,
                token_hash=token_hash,
                now=now,
            )
            db.commit()
        except HTTPException:
            raise
        except Exception:
            db.rollback()
            logger.exception(
                "Password reset request flow failed for email=%s",
                payload.email,
            )

    @staticmethod
    def confirm_password_reset(
        db: Session,
        payload: PasswordResetConfirm,
    ) -> None:
        now = utcnow()
        token_hash = hash_password_reset_token(payload.token)

        try:
            token_row = (
                db.query(PasswordResetToken)
                .filter(PasswordResetToken.token_hash == token_hash)
                .with_for_update()
                .first()
            )
            if not token_row or token_row.used_at is not None or token_row.expires_at <= now:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired password reset token",
                )

            user = db.query(User).filter(User.id == token_row.user_id).first()
            if not user or not user.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid or expired password reset token",
                )

            user.password_hash = get_password_hash(payload.new_password)
            token_row.used_at = now
            AuthService._invalidate_active_password_reset_tokens(
                db,
                user_id=token_row.user_id,
                now=now,
                exclude_token_hash=token_row.token_hash,
            )
            AuthService.revoke_all_user_refresh_sessions(
                db,
                user_id=user.id,
                reason="password_reset",
            )
            db.commit()
            logger.info("Password reset completed for user_id=%s", user.id)
        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception("Password reset confirm flow failed")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to reset password right now",
            )
