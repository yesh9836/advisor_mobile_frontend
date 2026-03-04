#!/usr/bin/env python3
"""
Process a single batch of pending Stripe plan cleanup outbox rows.

Usage:
  cd backend
  python scripts/process_stripe_plan_cleanup_outbox.py
"""

import json
import logging

from app.db.session import SessionLocal
from app.db.timezone import utcnow
from app.services.stripe_plan_cleanup_outbox_service import StripePlanCleanupOutboxService
from app.services.stripe_webhook_health_service import StripeWebhookHealthService

logger = logging.getLogger(__name__)


def process_cleanup_batch_with_heartbeat() -> dict:
    started_at = utcnow()
    heartbeat_db = SessionLocal()
    try:
        try:
            StripeWebhookHealthService.record_worker_started(
                heartbeat_db,
                source=StripePlanCleanupOutboxService.WORKER_HEARTBEAT_SOURCE,
                started_at=started_at,
            )
        except Exception as exc:
            logger.exception("Failed to record Stripe cleanup worker start heartbeat: %s", exc)
    finally:
        heartbeat_db.close()

    summary = None
    error_message = None
    db = SessionLocal()
    try:
        reclaim_summary = StripePlanCleanupOutboxService.reclaim_stale_processing_rows(db)
        if reclaim_summary.get("stale_selected", 0) > 0:
            logger.warning("Reclaimed stale Stripe cleanup outbox rows: %s", reclaim_summary)
        summary = StripePlanCleanupOutboxService.process_outbox_batch(db)
    except Exception as exc:
        error_message = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        db.close()

        heartbeat_db = SessionLocal()
        try:
            try:
                StripeWebhookHealthService.record_worker_finished(
                    heartbeat_db,
                    source=StripePlanCleanupOutboxService.WORKER_HEARTBEAT_SOURCE,
                    completed_at=utcnow(),
                    summary=summary if isinstance(summary, dict) else None,
                    error=error_message,
                )
            except Exception as exc:
                logger.exception("Failed to record Stripe cleanup worker finish heartbeat: %s", exc)
        finally:
            heartbeat_db.close()

    return summary or {}


def main() -> int:
    summary = process_cleanup_batch_with_heartbeat()
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
