import logging
from typing import Annotated, Generator

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.timezone import utcnow
from app.models.auth_session import RefreshTokenSession
from app.db.session import SessionLocal
from app.models.user import User
from app.schemas.auth import TokenData

logger = logging.getLogger(__name__)
_CSRF_PROTECTED_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def validate_csrf_for_cookie_auth(
    request: Request,
    *,
    enforce_method_check: bool = True,
) -> None:
    if enforce_method_check and request.method.upper() not in _CSRF_PROTECTED_METHODS:
        return

    csrf_cookie = request.cookies.get(settings.AUTH_CSRF_COOKIE_NAME)
    csrf_header = request.headers.get(settings.AUTH_CSRF_HEADER_NAME)
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token validation failed",
        )


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)]
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = request.cookies.get(settings.AUTH_ACCESS_COOKIE_NAME)
        if not token:
            raise credentials_exception

        validate_csrf_for_cookie_auth(request)
        
        payload = decode_access_token(token)
        token_data = TokenData.model_validate(payload)
        if token_data.token_type != "access":
            logger.warning("Token payload has unsupported token type")
            raise credentials_exception
        if token_data.user_id is None or not token_data.family_id:
            logger.warning("Token payload missing uid/fid claims")
            raise credentials_exception

    except (JWTError, ValidationError) as e:
        logger.warning(f"JWT validation failed: {e}")
        raise credentials_exception
    
    user = db.query(User).filter(User.id == token_data.user_id).first()
    
    if user is None:
        logger.warning(f"User not found for id: {token_data.user_id}")
        raise credentials_exception

    active_family = (
        db.query(RefreshTokenSession.id)
        .filter(
            RefreshTokenSession.user_id == token_data.user_id,
            RefreshTokenSession.family_id == token_data.family_id,
            RefreshTokenSession.revoked_at.is_(None),
            RefreshTokenSession.expires_at > utcnow(),
        )
        .first()
    )
    if active_family is None:
        logger.warning(
            "Token family is revoked or expired for user_id=%s family_id=%s",
            token_data.user_id,
            token_data.family_id,
        )
        raise credentials_exception
    
    return user


def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    if not current_user.is_active:
        logger.warning(
            "Inactive account access attempt by user %s (%s)",
            current_user.id,
            current_user.email,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    return current_user


def require_admin(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    if current_user.role != "admin":
        logger.warning(
            f"Unauthorized admin access attempt by user {current_user.id} "
            f"({current_user.email}) with role '{current_user.role}'"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    return current_user


def require_advisor(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    if current_user.role != "advisor":
        logger.warning(
            "Unauthorized advisor access attempt by user %s (%s) with role '%s'",
            current_user.id,
            current_user.email,
            current_user.role,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Advisor access required",
        )

    return current_user
