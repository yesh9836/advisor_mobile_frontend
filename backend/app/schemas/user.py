"""
User schemas for request/response validation.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserBase(BaseModel):
    """
    Base user schema with common fields.
    """
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=150)
    phone: Optional[str] = Field(None, max_length=50)


class UserCreate(UserBase):
    """
    Schema for creating a new user (includes password).
    """
    password: str = Field(..., min_length=8)


class UserUpdate(BaseModel):
    """
    Schema for updating user information (all fields optional).
    """
    email: Optional[EmailStr] = None
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    phone: Optional[str] = Field(None, max_length=50)
    password: Optional[str] = Field(None, min_length=8)


class UserResponse(BaseModel):
    """
    Schema for user response (excludes sensitive data like password).
    """
    id: int
    email: str
    name: str
    phone: Optional[str]
    role: str
    stripe_customer_id: Optional[str]
    created_at: datetime
    
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "examples": [
                {
                    "id": 1,
                    "email": "advisor@example.com",
                    "name": "John Doe",
                    "phone": "+1234567890",
                    "role": "advisor",
                    "stripe_customer_id": "cus_abc123",
                    "created_at": "2024-01-15T10:30:00Z"
                }
            ]
        }
    }