import logging
from typing import Any, Dict, Optional

from app.db.session import SessionLocal
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    """
    Best-effort audit logging.
    Uses an isolated session so business transactions are not blocked by audit failures.
    """

    @staticmethod
    def log_event(
        *,
        actor_user_id: int,
        action: str,
        entity_type: str,
        entity_id: Optional[int] = None,
        meta_data: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        db = SessionLocal()
        try:
            db.add(
                AuditLog(
                    actor_user_id=actor_user_id,
                    action=action,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    meta_data=meta_data,
                    ip_address=ip_address,
                )
            )
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.error("Failed to write audit log: %s", exc)
        finally:
            db.close()
