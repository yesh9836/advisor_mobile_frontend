import re
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.utils.phone import normalize_phone_number

_US_E164_PHONE_PATTERN = re.compile(r"^\+1\d{10}$")


def _normalize_email_value(value: object) -> object:
    if isinstance(value, str):
        return value.strip().lower()
    return value


class UserRegister(BaseModel):
    """
    Schema for user registration.
    """
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
    name: str = Field(..., min_length=1, max_length=150)
    phone: Optional[str] = Field(None, max_length=50)
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "advisor@example.com",
                    "password": "securepassword123",
                    "name": "John Doe",
                    "phone": "+13055551234",
                    "role": "advisor"
                }
            ]
        }
    }

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return _normalize_email_value(value)

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_and_validate_phone(cls, value: object) -> object:
        if value is None:
            return None

        normalized = normalize_phone_number(str(value))
        if normalized is None:
            return None

        if not _US_E164_PHONE_PATTERN.fullmatch(normalized):
            raise ValueError("Phone must be a valid US number")
        return normalized


class UserLogin(BaseModel):
    """
    Schema for user login.
    """
    email: EmailStr
    password: str
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "advisor@example.com",
                    "password": "securepassword123"
                }
            ]
        }
    }

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return _normalize_email_value(value)


class TokenData(BaseModel):
    """
    Schema for decoded token data.
    """
    email: Optional[str] = None
    user_id: Optional[int] = Field(default=None, alias="uid")
    family_id: Optional[str] = Field(default=None, alias="fid")
    token_type: Optional[str] = Field(default=None, alias="typ")

    model_config = {
        "populate_by_name": True,
    }


class PasswordResetRequest(BaseModel):
    """Schema for forgot-password request."""

    email: EmailStr

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return _normalize_email_value(value)


class PasswordResetRequestResponse(BaseModel):
    """Generic response for password reset requests."""

    message: str


class PasswordResetConfirm(BaseModel):
    """Schema for reset-password confirmation."""

    token: str = Field(..., min_length=16, max_length=512)
    new_password: str = Field(..., min_length=8, description="Password must be at least 8 characters")
