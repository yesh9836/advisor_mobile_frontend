from typing import Optional
from urllib.parse import quote_plus

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
    CORS_ALLOW_METHODS: list[str] = ["*"]
    CORS_ALLOW_HEADERS: list[str] = ["*"]

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_API_VERSION: str = "2023-10-16"

    # File uploads
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".jpg", ".jpeg", ".png"]

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
    RATE_LIMIT_PER_MINUTE: int = 60

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