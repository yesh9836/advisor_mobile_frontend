"""
API dependencies for database session management and authentication.
"""

import logging
from typing import Annotated, Generator

from fastapi import Depends, HTTPException, Request, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.db.session import SessionLocal
from app.models.user import User
from app.schemas.auth import TokenData

logger = logging.getLogger(__name__)


def _validate_csrf_for_cookie_auth(request: Request) -> None:
    if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:
        return

    csrf_cookie = request.cookies.get(settings.AUTH_CSRF_COOKIE_NAME)
    csrf_header = request.headers.get(settings.AUTH_CSRF_HEADER_NAME)
    if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token validation failed",
        )


def get_db() -> Generator[Session, None, None]:
    """
    Get database session.
    
    Yields:
        Database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)]
) -> User:
    """
    Get current authenticated user from JWT token.
    
    Args:
        request: Incoming request with auth cookies
        db: Database session
        
    Returns:
        Current authenticated User
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        token = request.cookies.get(settings.AUTH_ACCESS_COOKIE_NAME)
        if not token:
            raise credentials_exception

        _validate_csrf_for_cookie_auth(request)
        
        # Decode JWT token
        payload = decode_access_token(token)
        email: str = payload.get("sub")
        
        if email is None:
            logger.warning("Token payload missing 'sub' field")
            raise credentials_exception
        
        token_data = TokenData(email=email)
        
    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise credentials_exception
    
    # Get user from database
    user = db.query(User).filter(User.email == token_data.email).first()
    
    if user is None:
        logger.warning(f"User not found for email: {token_data.email}")
        raise credentials_exception
    
    return user


def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
) -> User:
    """
    Get current active user.
    
    This dependency can be extended to check if user is active/enabled
    if an is_active field is added to the User model in the future.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current active User
    """
    return current_user


def require_admin(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    """
    Require current user to be an admin.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Current user if they are an admin
        
    Raises:
        HTTPException: If user is not an admin (403 Forbidden)
    """
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
