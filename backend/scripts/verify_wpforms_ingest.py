#!/usr/bin/env python3
"""
Verify WPForms webhook ingestion by entry ID.

Usage:
  python scripts/verify_wpforms_ingest.py --entry-id entry-9001
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.models.lead import Lead, LeadIntakeWebhookEvent  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify WPForms webhook ingest by entry_id.")
    parser.add_argument("--entry-id", required=True, help="WPForms entry_id used for webhook ingest.")
    parser.add_argument(
        "--provider",
        default="wpforms",
        help="Provider key stored in lead_intake_webhook_events (default: wpforms).",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print JSON output.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    db = SessionLocal()
    try:
        row = (
            db.query(LeadIntakeWebhookEvent, Lead)
            .outerjoin(Lead, Lead.id == LeadIntakeWebhookEvent.lead_id)
            .filter(
                LeadIntakeWebhookEvent.provider == args.provider,
                LeadIntakeWebhookEvent.external_entry_id == args.entry_id,
            )
            .order_by(LeadIntakeWebhookEvent.id.desc())
            .first()
        )

        if row is None:
            payload = {
                "found": False,
                "provider": args.provider,
                "entry_id": args.entry_id,
            }
            print(json.dumps(payload, indent=2 if args.pretty else None))
            return 2

        event, lead = row
        payload = {
            "found": True,
            "provider": event.provider,
            "entry_id": event.external_entry_id,
            "payload_hash": event.payload_hash,
            "event_created_at": event.created_at.isoformat() if event.created_at else None,
            "lead_id": event.lead_id,
            "lead": None,
        }
        if lead is not None:
            payload["lead"] = {
                "id": lead.id,
                "source": lead.source,
                "state_code": lead.state_code,
                "zip_code": lead.zip_code,
                "first_name": lead.first_name,
                "last_name": lead.last_name,
                "mobile_phone": lead.mobile_phone,
                "preferred_follow_up_method": lead.preferred_follow_up_method,
                "best_time_to_reach": lead.best_time_to_reach,
                "created_at": lead.created_at.isoformat() if lead.created_at else None,
            }

        print(json.dumps(payload, indent=2 if args.pretty else None))
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
