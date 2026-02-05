"""
Authentication service containing business logic for user registration and authentication.
"""

import logging
from datetime import timedelta
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.user import User
from app.schemas.auth import UserRegister, UserLogin, Token

logger = logging.getLogger(__name__)


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
    def login_user(db: Session, credentials: UserLogin) -> Token:
        """
        Authenticate user and generate JWT token.
        """
        try:
            # 1. Verify User
            user = db.query(User).filter(User.email == credentials.email).first()
            
            if not user or not verify_password(credentials.password, user.password_hash):
                logger.warning(f"Login failed: Invalid credentials for {credentials.email}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect email or password",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            # 2. Generate Token
            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": user.email},
                expires_delta=access_token_expires
            )
            
            logger.info(f"Login successful for email: {credentials.email}")
            return Token(access_token=access_token, token_type="bearer")

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Login error for {credentials.email}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error during login"
            )