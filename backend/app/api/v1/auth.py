"""
Authentication API endpoints.
"""

import logging
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User
from app.schemas.auth import Token, UserLogin, UserRegister
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new advisor or admin account"
)
def register(
    user_data: UserRegister,
    db: Annotated[Session, Depends(get_db)]
) -> User:
    """
    Register a new user account.
    
    Args:
        user_data: User registration data
        db: Database session
        
    Returns:
        Created user (without password)
        
    Raises:
        HTTPException: If email already exists or registration fails
    """
    logger.info(f"Registration attempt for email: {user_data.email}")
    return AuthService.register_user(db, user_data)


@router.post(
    "/login",
    response_model=Token,
    summary="Login",
    description="Authenticate and receive JWT access token"
)
def login(
    credentials: UserLogin,
    db: Annotated[Session, Depends(get_db)]
) -> Token:
    """
    Authenticate user and return JWT access token.
    
    Args:
        credentials: User login credentials
        db: Database session
        
    Returns:
        JWT access token
        
    Raises:
        HTTPException: If credentials are invalid
    """
    logger.info(f"Login attempt for email: {credentials.email}")
    return AuthService.login_user(db, credentials)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get information about the currently authenticated user"
)
def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    """
    Get current authenticated user information.
    
    Args:
        current_user: Current authenticated user from JWT token
        
    Returns:
        Current user information (without password)
    """
    return current_user