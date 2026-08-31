#!/usr/bin/env python3
"""
Continuously reconcile Stripe events and process webhook inbox batches.

Usage:
  cd backend
  python scripts/run_stripe_webhook_pipeline.py
  python scripts/run_stripe_webhook_pipeline.py --poll-interval-seconds 2 --reconcile-interval-seconds 30
  python scripts/run_stripe_webhook_pipeline.py --cleanup-interval-seconds 15
"""

import argparse
import json
import logging
import time
from typing import Dict, Optional

from app.core.config import settings
from app.core.sentry import capture_exception, init_sentry
from app.db.session import SessionLocal
from app.db.timezone import utcnow
from app.services.stripe_reconciliation_service import StripeReconciliationService
from app.services.stripe_webhook_health_service import StripeWebhookHealthService
from app.services.stripe_webhook_inbox_service import StripeWebhookInboxService
from scripts.process_stripe_plan_cleanup_outbox import process_cleanup_batch_with_heartbeat

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run a loop that periodically reconciles Stripe events and drains the webhook inbox worker queue."
        )
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=float,
        default=5.0,
        help="Idle sleep between loop iterations when no immediate inbox work exists (default: 5).",
    )
    parser.add_argument(
        "--reconcile-interval-seconds",
        type=float,
        default=60.0,
        help="How often to run Stripe reconciliation backfill (default: 60).",
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=0,
        help="Optional finite number of loop cycles (0 means run forever).",
    )
    parser.add_argument(
        "--cleanup-interval-seconds",
        type=float,
        default=15.0,
        help="How often to run Stripe plan cleanup outbox processing (default: 15).",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Log verbosity (default: INFO).",
    )
    return parser.parse_args()


def _process_inbox_batch_with_heartbeat() -> Dict[str, int]:
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

    return summary or {
        "selected": 0,
        "processed": 0,
        "retried": 0,
        "failed": 0,
        "non_retryable": 0,
    }


def _run_reconciliation_once() -> Optional[Dict[str, int]]:
    try:
        summary = StripeReconciliationService.run_once_threadsafe()
    except Exception as exc:
        logger.exception("Stripe reconciliation cycle failed")
        capture_exception(
            exc,
            tags={"worker": "stripe-webhook-pipeline", "operation": "reconcile"},
        )
        return None
    logger.info("Stripe reconciliation summary: %s", json.dumps(summary, sort_keys=True))
    return summary


def main() -> int:
    init_sentry(service_name="stripe-webhook-pipeline-worker")
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    poll_interval_seconds = max(float(args.poll_interval_seconds), 0.1)
    reconcile_interval_seconds = max(float(args.reconcile_interval_seconds), 1.0)
    cleanup_interval_seconds = max(float(args.cleanup_interval_seconds), 0.5)
    max_cycles = max(int(args.max_cycles), 0)

    cycle = 0
    next_reconcile_at = 0.0
    next_cleanup_at = 0.0

    logger.info(
        (
            "Starting Stripe pipeline loop: poll_interval_seconds=%s "
            "reconcile_interval_seconds=%s cleanup_interval_seconds=%s max_cycles=%s"
        ),
        poll_interval_seconds,
        reconcile_interval_seconds,
        cleanup_interval_seconds,
        max_cycles or "infinite",
    )

    if settings.STRIPE_DEMO_MODE:
        logger.info(
            "Stripe reconciliation is disabled while STRIPE_DEMO_MODE is enabled; "
            "webhook inbox and cleanup processing remain active."
        )

    try:
        while True:
            now_monotonic = time.monotonic()
            if not settings.STRIPE_DEMO_MODE and now_monotonic >= next_reconcile_at:
                _run_reconciliation_once()
                next_reconcile_at = now_monotonic + reconcile_interval_seconds

            batch_summary = None
            try:
                batch_summary = _process_inbox_batch_with_heartbeat()
            except Exception as exc:
                logger.exception("Stripe webhook inbox processing cycle failed")
                capture_exception(
                    exc,
                    tags={"worker": "stripe-webhook-pipeline", "operation": "inbox_batch"},
                )
            else:
                logger.info("Stripe inbox batch summary: %s", json.dumps(batch_summary, sort_keys=True))

            cleanup_summary = None
            now_monotonic = time.monotonic()
            if now_monotonic >= next_cleanup_at:
                try:
                    cleanup_summary = process_cleanup_batch_with_heartbeat()
                except Exception as exc:
                    logger.exception("Stripe cleanup outbox processing cycle failed")
                    capture_exception(
                        exc,
                        tags={"worker": "stripe-webhook-pipeline", "operation": "cleanup_batch"},
                    )
                else:
                    logger.info("Stripe cleanup batch summary: %s", json.dumps(cleanup_summary, sort_keys=True))
                next_cleanup_at = now_monotonic + cleanup_interval_seconds

            cycle += 1
            if max_cycles and cycle >= max_cycles:
                break

            inbox_selected = int((batch_summary or {}).get("selected", 0))
            cleanup_selected = int((cleanup_summary or {}).get("selected", 0))
            if inbox_selected > 0 or cleanup_selected > 0:
                continue
            time.sleep(poll_interval_seconds)
    except KeyboardInterrupt:
        logger.info("Stopping Stripe pipeline loop")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
