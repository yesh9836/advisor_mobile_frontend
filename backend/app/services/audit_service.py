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

    @staticmethod
    def log_purchase_event(
        *,
        actor_user_id: int,
        action: str,
        purchase_id: Optional[int],
        credits_delta: Optional[int] = None,
        amount_cents: Optional[int] = None,
        correlation_ids: Optional[Dict[str, Any]] = None,
        meta_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        metadata: Dict[str, Any] = dict(meta_data or {})
        metadata["event_schema"] = "purchase_audit.v1"
        if credits_delta is not None:
            metadata["credits_delta"] = int(credits_delta)
        if amount_cents is not None:
            metadata["amount_cents"] = int(amount_cents)

        if correlation_ids:
            metadata["correlation_ids"] = {
                str(key): value
                for key, value in correlation_ids.items()
                if value is not None
            }

        AuditService.log_event(
            actor_user_id=actor_user_id,
            action=action,
            entity_type="LeadPurchase",
            entity_id=purchase_id,
            meta_data=metadata,
        )
