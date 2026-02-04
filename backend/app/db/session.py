from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections before using
    echo=settings.DB_ECHO,  # Log SQL queries (set to True for debugging)
)

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency for main database sessions.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- WordPress Database (For Import Tool) ---

def get_wordpress_engine():
    """
    Creates an engine specifically for the WordPress import.
    Returns None if WP credentials are not configured.
    """
    wp_url = settings.WORDPRESS_DATABASE_URL
    if not wp_url:
        return None
        
    return create_engine(
        wp_url,
        pool_pre_ping=True,
        echo=settings.DB_ECHO
    )

def get_wordpress_session() -> Generator[Session, None, None]:
    """
    Dependency or context manager for WordPress data import.
    """
    wp_engine = get_wordpress_engine()
    if not wp_engine:
        raise RuntimeError("WordPress database credentials are not configured.")
        
    WPSession = sessionmaker(bind=wp_engine)
    session = WPSession()
    try:
        yield session
    finally:
        session.close()