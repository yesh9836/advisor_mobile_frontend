import json
from ipaddress import ip_address, ip_network
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus
from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    
    Uses .env file in development, environment variables in production.
    """

    model_config = SettingsConfigDict(
        env_file=str(_BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    APP_ENV: str = "development"  # development | test | staging | production
    APP_NAME: str = "Spectaculeads"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_DOCS_ENABLED: bool = True
    API_DOCS_IN_PRODUCTION: bool = False
    SENTRY_DSN: Optional[str] = None
    SENTRY_ENVIRONMENT: Optional[str] = None
    SENTRY_RELEASE: Optional[str] = None
    SENTRY_SEND_DEFAULT_PII: bool = False
    SENTRY_ATTACH_STACKTRACE: bool = True
    SENTRY_TRACES_SAMPLE_RATE: float = 0.0
    SENTRY_PROFILES_SAMPLE_RATE: float = 0.0
    SENTRY_MAX_BREADCRUMBS: int = 100

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
    HEALTH_READY_DB_TIMEOUT_SECONDS: float = 2.0

    # Security - JWT
    SECRET_KEY: str = "change-this-to-a-secure-random-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    PASSWORD_RESET_REQUESTS_PER_HOUR: int = 3

    # Auth cookies
    AUTH_ACCESS_COOKIE_NAME: str = "access_token"
    AUTH_REFRESH_COOKIE_NAME: str = "refresh_token"
    AUTH_CSRF_COOKIE_NAME: str = "csrf_token"
    AUTH_COOKIE_DOMAIN: Optional[str] = None
    AUTH_COOKIE_SECURE: bool = False
    AUTH_COOKIE_SAMESITE: str = "lax"  # "lax" | "strict" | "none"
    AUTH_ACCESS_COOKIE_PATH: str = "/api/v1"
    AUTH_REFRESH_COOKIE_PATH: str = "/api/v1/auth"
    AUTH_CSRF_COOKIE_PATH: str = "/"
    AUTH_CSRF_HEADER_NAME: str = "X-CSRF-Token"

    # Password hashing
    PWD_SCHEME: str = "argon2"  # or "changed: "bcrypt" -> "argon2"
    PWD_DEPRECATED: str = "auto"

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: list[str] = [
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "X-CSRF-Token",
    ]

    FRONTEND_URL: str = "http://localhost:3000"

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_API_VERSION: str = "2023-10-16"
    STRIPE_REQUEST_TIMEOUT_SECONDS: float = 30.0
    STRIPE_MAX_NETWORK_RETRIES: int = 2
    STRIPE_CHECKOUT_SESSION_EXPIRES_MINUTES: int = 30
    STRIPE_WEBHOOK_EXPECT_LIVEMODE: Optional[bool] = None
    STRIPE_WEBHOOK_FAST_ACK_ENABLED: bool = True
    STRIPE_WEBHOOK_INBOX_BATCH_SIZE: int = 100
    STRIPE_WEBHOOK_INBOX_MAX_ATTEMPTS: int = 10
    STRIPE_WEBHOOK_INBOX_RETRY_BASE_SECONDS: int = 30
    STRIPE_WEBHOOK_INBOX_RETRY_MAX_SECONDS: int = 1800
    STRIPE_WEBHOOK_HEALTH_HEARTBEAT_MAX_AGE_SECONDS: int = 600
    STRIPE_WEBHOOK_HEALTH_MAX_DUE_PENDING_COUNT: int = 1000
    STRIPE_WEBHOOK_HEALTH_MAX_OLDEST_DUE_PENDING_SECONDS: int = 600
    STRIPE_WEBHOOK_HEALTH_MAX_FAILED_COUNT: int = 0
    STRIPE_WEBHOOK_HEALTH_STALE_LOCK_SECONDS: int = 900
    STRIPE_WEBHOOK_HEALTH_MAX_STALE_LOCK_COUNT: int = 0
    STRIPE_RECONCILIATION_LOOKBACK_SECONDS: int = 86400
    STRIPE_RECONCILIATION_SAFETY_WINDOW_SECONDS: int = 300
    STRIPE_RECONCILIATION_PAGE_SIZE: int = 100
    STRIPE_PLAN_CLEANUP_OUTBOX_BATCH_SIZE: int = 100
    STRIPE_PLAN_CLEANUP_OUTBOX_MAX_ATTEMPTS: int = 10
    STRIPE_PLAN_CLEANUP_RETRY_BASE_SECONDS: int = 30
    STRIPE_PLAN_CLEANUP_RETRY_MAX_SECONDS: int = 1800
    STRIPE_PLAN_CLEANUP_STALE_LOCK_SECONDS: int = 900
    STRIPE_PLAN_CLEANUP_HEALTH_HEARTBEAT_MAX_AGE_SECONDS: int = 600
    STRIPE_PLAN_CLEANUP_HEALTH_MAX_DUE_PENDING_COUNT: int = 1000
    STRIPE_PLAN_CLEANUP_HEALTH_MAX_OLDEST_DUE_PENDING_SECONDS: int = 600
    STRIPE_PLAN_CLEANUP_HEALTH_MAX_FAILED_COUNT: int = 0
    STRIPE_PLAN_CLEANUP_HEALTH_MAX_STALE_LOCK_COUNT: int = 0

    # Public website intake webhook (WPForms via relay)
    WPFORMS_WEBHOOK_HMAC_SECRET: str = ""
    WPFORMS_WEBHOOK_SIGNATURE_HEADER: str = "X-Webhook-Signature"
    WPFORMS_WEBHOOK_TIMESTAMP_HEADER: str = "X-Webhook-Timestamp"
    WPFORMS_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS: int = 300
    WPFORMS_WEBHOOK_ALLOW_BODY_ONLY_SIGNATURE: bool = False

    # Public advisor intake webhook (Elementor/WordPress via signed relay)
    ADVISOR_INTAKE_WEBHOOK_HMAC_SECRET: str = ""
    ADVISOR_INTAKE_WEBHOOK_SIGNATURE_HEADER: str = "X-Webhook-Signature"
    ADVISOR_INTAKE_WEBHOOK_TIMESTAMP_HEADER: str = "X-Webhook-Timestamp"
    ADVISOR_INTAKE_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS: int = 300

    # One-time purchase rollout controls
    ONE_TIME_PURCHASES_ENABLED: bool = True
    PURCHASE_WEBHOOK_CREDIT_GRANT_ENABLED: bool = True
    ONE_TIME_PURCHASES_ROLLOUT_USER_IDS: list[int] = []
    ONE_TIME_PURCHASES_ROLLOUT_EMAILS: list[str] = []

    # File uploads
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 10  # MB
    MAX_CSV_UPLOAD_SIZE: int = 5 * 1024 * 1024  # 5MB
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".jpg", ".jpeg", ".png"]
    ALLOWED_UPLOAD_MIME_TYPES: list[str] = [
        "application/pdf",
        "image/jpeg",
        "image/jpg",
        "image/png",
    ]
    LICENSE_RESUBMISSION_MAX_ATTEMPTS: int = 3
    LICENSE_RESUBMISSION_WINDOW_DAYS: int = 90
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
    SENDGRID_API_KEY: Optional[str] = None

    # Notifications
    NOTIFICATIONS_ENABLED: bool = False
    NOTIFICATION_EMAIL_ENABLED: bool = True
    NOTIFICATION_SMS_ENABLED: bool = True
    NOTIFICATION_EMAIL_PROVIDER: str = "smtp2go"  # smtp2go 
    NOTIFICATION_SMS_PROVIDER: str = "twilio"  # twilio 
    NOTIFICATION_FROM_EMAIL: Optional[str] = None
    NOTIFICATION_FROM_NAME: Optional[str] = None
    NOTIFICATION_OUTBOX_BATCH_SIZE: int = 100
    NOTIFICATION_OUTBOX_MAX_ATTEMPTS: int = 5
    NOTIFICATION_RETRY_BASE_SECONDS: int = 30
    NOTIFICATION_RETRY_MAX_SECONDS: int = 1800
    NOTIFICATION_OUTBOX_HEALTH_HEARTBEAT_MAX_AGE_SECONDS: int = 600
    NOTIFICATION_OUTBOX_HEALTH_MAX_DUE_PENDING_COUNT: int = 1000
    NOTIFICATION_OUTBOX_HEALTH_MAX_OLDEST_DUE_PENDING_SECONDS: int = 600
    NOTIFICATION_OUTBOX_HEALTH_MAX_FAILED_COUNT: int = 0
    NOTIFICATION_OUTBOX_HEALTH_STALE_LOCK_SECONDS: int = 900
    NOTIFICATION_OUTBOX_HEALTH_MAX_STALE_LOCK_COUNT: int = 0

    # Operational data retention
    OPERATIONAL_RETENTION_BATCH_SIZE: int = 500
    PASSWORD_RESET_REQUEST_ATTEMPT_RETENTION_DAYS: int = 30
    PASSWORD_RESET_TOKEN_RETENTION_DAYS: int = 30
    NOTIFICATION_OUTBOX_RETENTION_DAYS: int = 90
    PROCESSED_STRIPE_EVENT_RETENTION_DAYS: int = 90

    # Twilio SMS
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_MESSAGING_SERVICE_SID: Optional[str] = None
    TWILIO_FROM_NUMBER: Optional[str] = None

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

    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_BACKEND: str = "redis"  # redis
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    RATE_LIMIT_PREFIX: str = "lm:rl"
    RATE_LIMIT_FAIL_OPEN: bool = False

    RATE_LIMIT_LOGIN_TIMES: int = 5
    RATE_LIMIT_LOGIN_SECONDS: int = 60
    RATE_LIMIT_REGISTER_TIMES: int = 5
    RATE_LIMIT_REGISTER_SECONDS: int = 300
    RATE_LIMIT_REFRESH_TIMES: int = 20
    RATE_LIMIT_REFRESH_SECONDS: int = 60
    RATE_LIMIT_AUTH_PASSWORD_RESET_ROUTE_TIMES: int = 20
    RATE_LIMIT_AUTH_PASSWORD_RESET_ROUTE_SECONDS: int = 60
    RATE_LIMIT_WPFORMS_WEBHOOK_TIMES: int = 120
    RATE_LIMIT_WPFORMS_WEBHOOK_SECONDS: int = 60
    RATE_LIMIT_ADVISOR_INTAKE_WEBHOOK_TIMES: int = 120
    RATE_LIMIT_ADVISOR_INTAKE_WEBHOOK_SECONDS: int = 60

    # Legacy global limiter knobs (deprecated but retained for compatibility).
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_WINDOW_SECONDS: int = 60
    # Proxy header trust is disabled by default; enable only behind known proxies.
    RATE_LIMIT_TRUST_PROXY_HEADERS: bool = False
    # Comma-separated or JSON array of IP/CIDR values.
    RATE_LIMIT_TRUSTED_PROXIES: list[str] = []

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @property
    def UPLOAD_ROOT(self) -> Path:
        """
        Canonical absolute upload root.

        Relative UPLOAD_DIR values are anchored to the backend root so upload
        behavior does not vary with process working directory.
        """
        configured = Path(self.UPLOAD_DIR).expanduser()
        if configured.is_absolute():
            return configured.resolve(strict=False)
        return (_BACKEND_ROOT / configured).resolve(strict=False)

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

    @field_validator("RATE_LIMIT_TRUSTED_PROXIES", mode="before")
    @classmethod
    def parse_trusted_proxies(cls, value):
        if isinstance(value, str):
            parsed = value.strip()
            if not parsed:
                return []
            if parsed.startswith("["):
                return json.loads(parsed)
            return [item.strip() for item in parsed.split(",") if item.strip()]
        return value

    @field_validator("ONE_TIME_PURCHASES_ROLLOUT_USER_IDS", mode="before")
    @classmethod
    def parse_rollout_user_ids(cls, value):
        if isinstance(value, str):
            parsed = value.strip()
            if not parsed:
                return []
            if parsed.startswith("["):
                value = json.loads(parsed)
            else:
                value = [item.strip() for item in parsed.split(",") if item.strip()]

        if isinstance(value, (tuple, set)):
            value = list(value)

        if value is None:
            return []

        if isinstance(value, list):
            return [int(item) for item in value]

        return value

    @field_validator("ONE_TIME_PURCHASES_ROLLOUT_EMAILS", mode="before")
    @classmethod
    def parse_rollout_emails(cls, value):
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

    @field_validator(
        "RATE_LIMIT_PER_MINUTE",
        "RATE_LIMIT_WINDOW_SECONDS",
        "RATE_LIMIT_LOGIN_TIMES",
        "RATE_LIMIT_LOGIN_SECONDS",
        "RATE_LIMIT_REGISTER_TIMES",
        "RATE_LIMIT_REGISTER_SECONDS",
        "RATE_LIMIT_REFRESH_TIMES",
        "RATE_LIMIT_REFRESH_SECONDS",
        "RATE_LIMIT_AUTH_PASSWORD_RESET_ROUTE_TIMES",
        "RATE_LIMIT_AUTH_PASSWORD_RESET_ROUTE_SECONDS",
        "RATE_LIMIT_WPFORMS_WEBHOOK_TIMES",
        "RATE_LIMIT_WPFORMS_WEBHOOK_SECONDS",
        "RATE_LIMIT_ADVISOR_INTAKE_WEBHOOK_TIMES",
        "RATE_LIMIT_ADVISOR_INTAKE_WEBHOOK_SECONDS",
        "LICENSE_RESUBMISSION_MAX_ATTEMPTS",
        "LICENSE_RESUBMISSION_WINDOW_DAYS",
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "REFRESH_TOKEN_EXPIRE_DAYS",
        "PASSWORD_RESET_TOKEN_EXPIRE_MINUTES",
        "PASSWORD_RESET_REQUESTS_PER_HOUR",
        "NOTIFICATION_OUTBOX_BATCH_SIZE",
        "NOTIFICATION_OUTBOX_MAX_ATTEMPTS",
        "NOTIFICATION_RETRY_BASE_SECONDS",
        "NOTIFICATION_RETRY_MAX_SECONDS",
        "NOTIFICATION_OUTBOX_HEALTH_HEARTBEAT_MAX_AGE_SECONDS",
        "NOTIFICATION_OUTBOX_HEALTH_MAX_OLDEST_DUE_PENDING_SECONDS",
        "NOTIFICATION_OUTBOX_HEALTH_STALE_LOCK_SECONDS",
        "STRIPE_WEBHOOK_INBOX_BATCH_SIZE",
        "STRIPE_WEBHOOK_INBOX_MAX_ATTEMPTS",
        "STRIPE_WEBHOOK_INBOX_RETRY_BASE_SECONDS",
        "STRIPE_WEBHOOK_INBOX_RETRY_MAX_SECONDS",
        "STRIPE_WEBHOOK_HEALTH_HEARTBEAT_MAX_AGE_SECONDS",
        "STRIPE_WEBHOOK_HEALTH_MAX_OLDEST_DUE_PENDING_SECONDS",
        "STRIPE_WEBHOOK_HEALTH_STALE_LOCK_SECONDS",
        "STRIPE_PLAN_CLEANUP_OUTBOX_BATCH_SIZE",
        "STRIPE_PLAN_CLEANUP_OUTBOX_MAX_ATTEMPTS",
        "STRIPE_PLAN_CLEANUP_RETRY_BASE_SECONDS",
        "STRIPE_PLAN_CLEANUP_RETRY_MAX_SECONDS",
        "STRIPE_PLAN_CLEANUP_STALE_LOCK_SECONDS",
        "STRIPE_PLAN_CLEANUP_HEALTH_HEARTBEAT_MAX_AGE_SECONDS",
        "STRIPE_PLAN_CLEANUP_HEALTH_MAX_OLDEST_DUE_PENDING_SECONDS",
        "OPERATIONAL_RETENTION_BATCH_SIZE",
        "PASSWORD_RESET_REQUEST_ATTEMPT_RETENTION_DAYS",
        "PASSWORD_RESET_TOKEN_RETENTION_DAYS",
        "NOTIFICATION_OUTBOX_RETENTION_DAYS",
        "PROCESSED_STRIPE_EVENT_RETENTION_DAYS",
        "WPFORMS_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS",
        "ADVISOR_INTAKE_WEBHOOK_TIMESTAMP_TOLERANCE_SECONDS",
        mode="after",
    )
    @classmethod
    def validate_rate_limit_bounds(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Configuration values must be greater than 0")
        return value

    @field_validator(
        "STRIPE_WEBHOOK_HEALTH_MAX_DUE_PENDING_COUNT",
        "STRIPE_WEBHOOK_HEALTH_MAX_FAILED_COUNT",
        "STRIPE_WEBHOOK_HEALTH_MAX_STALE_LOCK_COUNT",
        "NOTIFICATION_OUTBOX_HEALTH_MAX_DUE_PENDING_COUNT",
        "NOTIFICATION_OUTBOX_HEALTH_MAX_FAILED_COUNT",
        "NOTIFICATION_OUTBOX_HEALTH_MAX_STALE_LOCK_COUNT",
        "STRIPE_PLAN_CLEANUP_HEALTH_MAX_DUE_PENDING_COUNT",
        "STRIPE_PLAN_CLEANUP_HEALTH_MAX_FAILED_COUNT",
        "STRIPE_PLAN_CLEANUP_HEALTH_MAX_STALE_LOCK_COUNT",
        mode="after",
    )
    @classmethod
    def validate_non_negative_bounds(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Configuration values must be greater than or equal to 0")
        return value

    @field_validator("SENTRY_TRACES_SAMPLE_RATE", "SENTRY_PROFILES_SAMPLE_RATE", mode="after")
    @classmethod
    def validate_sentry_sample_rate(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("Sentry sample rates must be between 0 and 1")
        return value

    @field_validator("SENTRY_MAX_BREADCRUMBS", mode="after")
    @classmethod
    def validate_sentry_max_breadcrumbs(cls, value: int) -> int:
        if value < 0:
            raise ValueError("SENTRY_MAX_BREADCRUMBS must be greater than or equal to 0")
        return value

    @field_validator("STRIPE_CHECKOUT_SESSION_EXPIRES_MINUTES", mode="after")
    @classmethod
    def validate_checkout_session_expiration_minutes(cls, value: int) -> int:
        # Stripe checkout sessions must expire between 30 minutes and 24 hours.
        if value < 30 or value > 1440:
            raise ValueError(
                "STRIPE_CHECKOUT_SESSION_EXPIRES_MINUTES must be between 30 and 1440"
            )
        return value

    @field_validator("HEALTH_READY_DB_TIMEOUT_SECONDS", mode="after")
    @classmethod
    def validate_health_ready_db_timeout_seconds(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("HEALTH_READY_DB_TIMEOUT_SECONDS must be greater than 0")
        return value

    @field_validator("AUTH_COOKIE_SAMESITE", mode="after")
    @classmethod
    def validate_auth_cookie_samesite(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("AUTH_COOKIE_SAMESITE must be one of: lax, strict, none")
        return normalized

    @field_validator("RATE_LIMIT_BACKEND", mode="after")
    @classmethod
    def validate_rate_limit_backend(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"redis"}:
            raise ValueError("RATE_LIMIT_BACKEND must be 'redis'")
        return normalized

    @field_validator("RATE_LIMIT_TRUSTED_PROXIES", mode="after")
    @classmethod
    def validate_trusted_proxies(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for proxy in value:
            network = str(ip_network(proxy.strip(), strict=False))
            if network not in normalized:
                normalized.append(network)
        return normalized

    @field_validator("ONE_TIME_PURCHASES_ROLLOUT_USER_IDS", mode="after")
    @classmethod
    def validate_rollout_user_ids(cls, value: list[int]) -> list[int]:
        normalized: list[int] = []
        for user_id in value:
            parsed = int(user_id)
            if parsed <= 0:
                raise ValueError("ONE_TIME_PURCHASES_ROLLOUT_USER_IDS must contain positive user IDs")
            if parsed not in normalized:
                normalized.append(parsed)
        return normalized

    @field_validator("NOTIFICATION_EMAIL_PROVIDER", mode="after")
    @classmethod
    def validate_notification_email_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"smtp2go", "smtp", "sendgrid", "noop"}:
            raise ValueError("NOTIFICATION_EMAIL_PROVIDER must be one of: smtp2go, smtp, sendgrid, noop")
        return normalized

    @field_validator("NOTIFICATION_SMS_PROVIDER", mode="after")
    @classmethod
    def validate_notification_sms_provider(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in {"twilio", "noop"}:
            raise ValueError("NOTIFICATION_SMS_PROVIDER must be one of: twilio, noop")
        return normalized

    @field_validator("ONE_TIME_PURCHASES_ROLLOUT_EMAILS", mode="after")
    @classmethod
    def normalize_rollout_emails(cls, value: list[str]) -> list[str]:
        normalized: list[str] = []
        for email in value:
            lowered = email.strip().lower()
            if not lowered:
                continue
            if lowered not in normalized:
                normalized.append(lowered)
        return normalized

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

        frontend_url = (self.FRONTEND_URL or "").strip()
        parsed_frontend_url = urlparse(frontend_url)
        if parsed_frontend_url.scheme != "https" or not parsed_frontend_url.netloc:
            raise ValueError("FRONTEND_URL must be an absolute HTTPS URL in production")
        frontend_host = (parsed_frontend_url.hostname or "").strip().lower()
        if not frontend_host:
            raise ValueError("FRONTEND_URL must include a valid hostname in production")
        if frontend_host == "localhost" or frontend_host.endswith(".localhost"):
            raise ValueError("FRONTEND_URL localhost hostnames are not allowed in production")
        is_loopback_host = False
        try:
            is_loopback_host = ip_address(frontend_host).is_loopback
        except ValueError:
            pass
        if is_loopback_host:
            raise ValueError("FRONTEND_URL loopback hosts are not allowed in production")

        if "*" in self.CORS_ALLOW_METHODS or "*" in self.CORS_ALLOW_HEADERS or "*" in self.CORS_ORIGINS:
            raise ValueError("Wildcard CORS values are not allowed in production")

        if not self.AUTH_COOKIE_SECURE:
            raise ValueError("AUTH_COOKIE_SECURE must be enabled in production")

        if self.AUTH_COOKIE_SAMESITE == "none" and not self.AUTH_COOKIE_SECURE:
            raise ValueError("AUTH_COOKIE_SAMESITE=none requires AUTH_COOKIE_SECURE=true")

        if self.RATE_LIMIT_TRUST_PROXY_HEADERS and not self.RATE_LIMIT_TRUSTED_PROXIES:
            raise ValueError("RATE_LIMIT_TRUSTED_PROXIES is required when proxy header trust is enabled")

        if self.RATE_LIMIT_ENABLED and self.RATE_LIMIT_BACKEND == "redis" and not self.REDIS_URL:
            raise ValueError("REDIS_URL must be set when Redis-backed rate limiting is enabled")

        if self.NOTIFICATION_EMAIL_PROVIDER != "smtp2go":
            raise ValueError(
                "NOTIFICATION_EMAIL_PROVIDER must be 'smtp2go' in production"
            )

        smtp_host = (self.SMTP_HOST or "").strip().lower()
        smtp_host_without_port = smtp_host.split(":", 1)[0]
        if not smtp_host_without_port:
            raise ValueError("SMTP_HOST must be set in production")
        if not (
            smtp_host_without_port == "smtp2go.com"
            or smtp_host_without_port.endswith(".smtp2go.com")
        ):
            raise ValueError("SMTP_HOST must point to an SMTP2GO host in production")
        if not self.SMTP_PORT:
            raise ValueError("SMTP_PORT must be set in production")
        if not (self.NOTIFICATION_FROM_EMAIL or self.SMTP_FROM_EMAIL):
            raise ValueError("NOTIFICATION_FROM_EMAIL or SMTP_FROM_EMAIL must be set in production")

        if self.NOTIFICATION_SMS_PROVIDER != "twilio":
            raise ValueError(
                "NOTIFICATION_SMS_PROVIDER must be 'twilio' in production"
            )
        if not self.TWILIO_ACCOUNT_SID or not self.TWILIO_AUTH_TOKEN:
            raise ValueError("Twilio credentials must be configured in production")
        if not self.TWILIO_MESSAGING_SERVICE_SID and not self.TWILIO_FROM_NUMBER:
            raise ValueError(
                "TWILIO_MESSAGING_SERVICE_SID or TWILIO_FROM_NUMBER is required in production"
            )

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


settings = Settings()
