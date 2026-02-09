import json
from typing import Optional
from urllib.parse import quote_plus
from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Uses .env file in development, environment variables in production.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_ENV: str = "development"  # development | test | staging | production
    APP_NAME: str = "Lead Management System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "lead_management"
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_ECHO: bool = False

    # Security - JWT
    SECRET_KEY: str = "change-this-to-a-secure-random-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Password hashing
    PWD_SCHEME: str = "argon2"  # or "changed: "bcrypt" -> "argon2"
    PWD_DEPRECATED: str = "auto"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: list[str] = ["Authorization", "Content-Type", "Accept", "Origin"]

    FRONTEND_URL: str = "http://localhost:3000"

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_API_VERSION: str = "2023-10-16"

    # File uploads
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 10 * 1024 * 1024  # 10MB
    MAX_CSV_UPLOAD_SIZE: int = 5 * 1024 * 1024  # 5MB
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".jpg", ".jpeg", ".png"]
    ALLOWED_UPLOAD_MIME_TYPES: list[str] = [
        "application/pdf",
        "image/jpeg",
        "image/jpg",
        "image/png",
    ]
    ALLOWED_CSV_MIME_TYPES: list[str] = [
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
    ]

    # Email (optional - for future notifications)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = None
    SMTP_FROM_NAME: Optional[str] = None

    # WordPress (for one-time import)
    WP_DB_HOST: Optional[str] = None
    WP_DB_PORT: Optional[int] = None
    WP_DB_USER: Optional[str] = None
    WP_DB_PASSWORD: Optional[str] = None
    WP_DB_NAME: Optional[str] = None
    WP_TABLE_PREFIX: str = "wp_"

    # Admin
    INITIAL_ADMIN_EMAIL: str = "admin@example.com"
    INITIAL_ADMIN_PASSWORD: str = "change-this-password"
    INITIAL_ADMIN_NAME: str = "System Admin"

    # Pagination
    DEFAULT_PAGE_SIZE: int = 20
    MAX_PAGE_SIZE: int = 100

    # Rate limiting (requests per minute)
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, value):
        if isinstance(value, str):
            parsed = value.strip()
            if not parsed:
                return []
            if parsed.startswith("["):
                return json.loads(parsed)
            return [item.strip() for item in parsed.split(",") if item.strip()]
        return value

    @field_validator("ALLOWED_EXTENSIONS", mode="after")
    @classmethod
    def normalize_extensions(cls, value: list[str]) -> list[str]:
        normalized = []
        for ext in value:
            ext = ext.strip().lower()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = f".{ext}"
            if ext not in normalized:
                normalized.append(ext)
        return normalized

    @field_validator("RATE_LIMIT_PER_MINUTE", "RATE_LIMIT_WINDOW_SECONDS", mode="after")
    @classmethod
    def validate_rate_limit_bounds(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Rate limiting values must be greater than 0")
        return value

    @model_validator(mode="after")
    def validate_security_posture(self):
        if not self.is_production:
            return self

        weak_secret_markers = {"change-this", "changeme", "default", "secret", "password"}
        secret_key_lower = self.SECRET_KEY.lower()
        if len(self.SECRET_KEY) < 32 or any(marker in secret_key_lower for marker in weak_secret_markers):
            raise ValueError("SECRET_KEY must be a strong value in production (32+ chars, non-default)")

        password = self.INITIAL_ADMIN_PASSWORD
        if (
            len(password) < 12
            or password.lower() == password
            or password.upper() == password
            or not any(ch.isdigit() for ch in password)
            or not any(not ch.isalnum() for ch in password)
            or "change-this" in password.lower()
        ):
            raise ValueError("INITIAL_ADMIN_PASSWORD must be strong in production")

        if not self.DB_PASSWORD:
            raise ValueError("DB_PASSWORD must be set in production")

        if not self.STRIPE_SECRET_KEY or not self.STRIPE_WEBHOOK_SECRET:
            raise ValueError("Stripe secrets must be configured in production")

        if not self.CORS_ORIGINS:
            raise ValueError("CORS_ORIGINS must include trusted origins in production")

        for origin in self.CORS_ORIGINS:
            parsed = urlparse(origin)
            if parsed.scheme != "https":
                raise ValueError("CORS origins must use HTTPS in production")
            if "localhost" in parsed.netloc or "127.0.0.1" in parsed.netloc:
                raise ValueError("Localhost CORS origins are not allowed in production")

        if "*" in self.CORS_ALLOW_METHODS or "*" in self.CORS_ALLOW_HEADERS or "*" in self.CORS_ORIGINS:
            raise ValueError("Wildcard CORS values are not allowed in production")

        return self

    @property
    def DATABASE_URL(self) -> str:
        """
        Construct database URL from individual components.
        
        Returns:
            SQLAlchemy database URL for MySQL
        """
        user_encoded = quote_plus(self.DB_USER)
        password_encoded = quote_plus(self.DB_PASSWORD)

        return (
            f"mysql+pymysql://{user_encoded}:{password_encoded}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
            f"?charset=utf8mb4"
        )

    @property
    def WORDPRESS_DATABASE_URL(self) -> Optional[str]:
        """
        Construct WordPress database URL if credentials provided.
        
        Returns:
            SQLAlchemy database URL for WordPress MySQL database or None
        """
        if not all([self.WP_DB_HOST, self.WP_DB_USER, self.WP_DB_NAME]):
            return None

        user_encoded = quote_plus(self.WP_DB_USER)
        password_encoded = quote_plus(self.WP_DB_PASSWORD) if self.WP_DB_PASSWORD else ""

        return (
            f"mysql+pymysql://{user_encoded}:{password_encoded}"
            f"@{self.WP_DB_HOST}:{self.WP_DB_PORT or 3306}/{self.WP_DB_NAME}"
            f"?charset=utf8mb4"
        )


# Global settings instance
settings = Settings()
