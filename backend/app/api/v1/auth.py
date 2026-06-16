import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user, get_db, validate_csrf_for_cookie_auth
from app.core.config import settings
from app.core.rate_limit import (
    login_rate_limit_dependency,
    password_reset_route_rate_limit_dependency,
    refresh_rate_limit_dependency,
    register_rate_limit_dependency,
)
from app.models.user import User
from app.schemas.auth import (
    PasswordResetConfirm,
    PasswordResetRequest,
    PasswordResetRequestResponse,
    UserLogin,
    UserRegister,
)
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService, IssuedAuthTokens

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])
PASSWORD_RESET_GENERIC_MESSAGE = (
    "If an account exists for that email, password reset instructions will be sent."
)


def _set_auth_cookies(response: Response, tokens: IssuedAuthTokens) -> None:
    access_max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    refresh_max_age = settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

    response.set_cookie(
        key=settings.AUTH_ACCESS_COOKIE_NAME,
        value=tokens.access_token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=access_max_age,
        path=settings.AUTH_ACCESS_COOKIE_PATH,
        domain=settings.AUTH_COOKIE_DOMAIN,
    )
    response.set_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        value=tokens.refresh_token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=refresh_max_age,
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        domain=settings.AUTH_COOKIE_DOMAIN,
    )
    response.set_cookie(
        key=settings.AUTH_CSRF_COOKIE_NAME,
        value=tokens.csrf_token,
        httponly=False,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=refresh_max_age,
        path=settings.AUTH_CSRF_COOKIE_PATH,
        domain=settings.AUTH_COOKIE_DOMAIN,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(
        key=settings.AUTH_ACCESS_COOKIE_NAME,
        path=settings.AUTH_ACCESS_COOKIE_PATH,
        domain=settings.AUTH_COOKIE_DOMAIN,
    )
    response.delete_cookie(
        key=settings.AUTH_REFRESH_COOKIE_NAME,
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        domain=settings.AUTH_COOKIE_DOMAIN,
    )
    response.delete_cookie(
        key=settings.AUTH_CSRF_COOKIE_NAME,
        path=settings.AUTH_CSRF_COOKIE_PATH,
        domain=settings.AUTH_COOKIE_DOMAIN,
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(register_rate_limit_dependency)],
    summary="Register new user",
    description="Create a new advisor or admin account"
)
def register(
    user_data: UserRegister,
    db: Annotated[Session, Depends(get_db)]
) -> User:
    logger.info(f"Registration attempt for email: {user_data.email}")
    return AuthService.register_user(db, user_data)


@router.post(
    "/login",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(login_rate_limit_dependency)],
    summary="Login",
    description="Authenticate user and issue auth cookies"
)
def login(
    credentials: UserLogin,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)]
) -> Response:
    logger.info(f"Login attempt for email: {credentials.email}")
    issued_tokens = AuthService.login_and_issue_tokens(
        db,
        credentials,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    _set_auth_cookies(response, issued_tokens)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post(
    "/password-reset/request",
    response_model=PasswordResetRequestResponse,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(password_reset_route_rate_limit_dependency)],
    summary="Request password reset",
    description="Request a one-time password reset link for the account email.",
)
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> PasswordResetRequestResponse:
    AuthService.request_password_reset(
        db,
        payload,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    return PasswordResetRequestResponse(message=PASSWORD_RESET_GENERIC_MESSAGE)


@router.post(
    "/password-reset/confirm",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Confirm password reset",
    description="Confirm password reset with a valid one-time token.",
)
def confirm_password_reset(
    payload: PasswordResetConfirm,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    AuthService.confirm_password_reset(db, payload)
    _clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post(
    "/refresh",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(refresh_rate_limit_dependency)],
    summary="Refresh access token",
    description="Rotate refresh token and issue fresh auth cookies",
)
def refresh(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    refresh_token = request.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )
    validate_csrf_for_cookie_auth(request)
    issued_tokens = AuthService.refresh_tokens(
        db,
        refresh_token=refresh_token,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    _set_auth_cookies(response, issued_tokens)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout",
    description="Revoke refresh-token family and clear auth cookies",
)
def logout(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    refresh_token = request.cookies.get(settings.AUTH_REFRESH_COOKIE_NAME)
    if refresh_token:
        validate_csrf_for_cookie_auth(request)
    AuthService.logout_user(db, refresh_token=refresh_token)
    _clear_auth_cookies(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get information about the currently authenticated user"
)
def get_current_user_info(
    current_user: Annotated[User, Depends(get_current_active_user)]
) -> User:
    return current_user
