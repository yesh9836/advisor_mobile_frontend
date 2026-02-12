from typing import Optional

from pydantic import BaseModel, EmailStr, Field


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
                    "phone": "+1234567890",
                    "role": "advisor"
                }
            ]
        }
    }


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
