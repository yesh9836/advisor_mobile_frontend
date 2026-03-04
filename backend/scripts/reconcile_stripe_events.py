#!/usr/bin/env python3
"""
Scan Stripe events and enqueue missed business events into the webhook inbox.

Usage:
  cd backend
  python scripts/reconcile_stripe_events.py
"""

import json

from app.core.sentry import init_sentry
from app.services.stripe_reconciliation_service import StripeReconciliationService


def main() -> int:
    init_sentry(service_name="stripe-reconciliation-worker")
    summary = StripeReconciliationService.run_once_threadsafe()
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
