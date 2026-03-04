#!/usr/bin/env python3
"""
Process a single batch of pending notification outbox rows.

Usage:
  cd backend
  python scripts/process_notification_outbox.py
"""

import json
import logging

from app.db.session import SessionLocal
from app.db.timezone import utcnow
from app.services.notification_outbox_health_service import NotificationOutboxHealthService
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


def main() -> int:
    started_at = utcnow()
    heartbeat_db = SessionLocal()
    try:
        try:
            NotificationOutboxHealthService.record_worker_started(
                heartbeat_db,
                started_at=started_at,
            )
        except Exception as exc:
            logger.exception(
                "Failed to record notification outbox worker start heartbeat: %s",
                exc,
            )
    finally:
        heartbeat_db.close()

    summary = None
    error_message = None
    db = SessionLocal()
    try:
        reclaim_summary = NotificationService.reclaim_stale_processing_rows(db)
        if reclaim_summary.get("stale_selected", 0) > 0:
            logger.warning("Reclaimed stale notification outbox rows: %s", reclaim_summary)
        summary = NotificationService.process_outbox_batch(db)
    except Exception as exc:
        error_message = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        db.close()

        heartbeat_db = SessionLocal()
        try:
            try:
                NotificationOutboxHealthService.record_worker_finished(
                    heartbeat_db,
                    completed_at=utcnow(),
                    summary=summary if isinstance(summary, dict) else None,
                    error=error_message,
                )
            except Exception as exc:
                logger.exception(
                    "Failed to record notification outbox worker finish heartbeat: %s",
                    exc,
                )
        finally:
            heartbeat_db.close()

    print(json.dumps(summary or {}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
