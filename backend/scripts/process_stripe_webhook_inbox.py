#!/usr/bin/env python3
"""
Process a single batch of pending Stripe webhook inbox rows.

Usage:
  cd backend
  python scripts/process_stripe_webhook_inbox.py
"""

import json
import logging

from app.core.sentry import init_sentry
from app.db.session import SessionLocal
from app.db.timezone import utcnow
from app.services.stripe_webhook_health_service import StripeWebhookHealthService
from app.services.stripe_webhook_inbox_service import StripeWebhookInboxService

logger = logging.getLogger(__name__)


def main() -> int:
    init_sentry(service_name="stripe-webhook-inbox-worker")
    started_at = utcnow()
    heartbeat_db = SessionLocal()
    try:
        try:
            StripeWebhookHealthService.record_worker_started(
                heartbeat_db,
                started_at=started_at,
            )
        except Exception as exc:
            logger.exception("Failed to record Stripe webhook worker start heartbeat: %s", exc)
    finally:
        heartbeat_db.close()

    summary = None
    error_message = None
    db = SessionLocal()
    try:
        reclaim_summary = StripeWebhookInboxService.reclaim_stale_processing_rows(db)
        if reclaim_summary.get("stale_selected", 0) > 0:
            logger.warning("Reclaimed stale Stripe webhook inbox rows: %s", reclaim_summary)
        summary = StripeWebhookInboxService.process_inbox_batch(db)
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
                    completed_at=utcnow(),
                    summary=summary if isinstance(summary, dict) else None,
                    error=error_message,
                )
            except Exception as exc:
                logger.exception("Failed to record Stripe webhook worker finish heartbeat: %s", exc)
        finally:
            heartbeat_db.close()

    print(json.dumps(summary or {}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
