#!/usr/bin/env python3
"""
Run batched retention cleanup for operational tables.

Usage:
  cd backend
  python scripts/purge_operational_data.py
  python scripts/purge_operational_data.py --interval-seconds 3600
  python scripts/purge_operational_data.py --interval-seconds 300 --max-cycles 12
"""

import argparse
import json
import logging
import time
from typing import Dict

from app.core.sentry import capture_exception, init_sentry
from app.db.session import SessionLocal
from app.services.operational_retention_service import OperationalRetentionService

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run operational retention cleanup once (default), or in a loop when "
            "--interval-seconds is provided."
        )
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=0.0,
        help=(
            "When > 0, run in continuous mode and sleep this many seconds between cleanup cycles "
            "(default: 0 for one-shot)."
        ),
    )
    parser.add_argument(
        "--max-cycles",
        type=int,
        default=1,
        help=(
            "Maximum number of cleanup cycles in continuous mode. "
            "Use 0 to run forever (default: 1)."
        ),
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Log verbosity (default: INFO).",
    )
    return parser.parse_args()


def _purge_once() -> Dict[str, int]:
    db = SessionLocal()
    try:
        return OperationalRetentionService.purge_expired_operational_rows(db)
    finally:
        db.close()


def main() -> int:
    init_sentry(service_name="operational-retention-worker")
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    interval_seconds = max(float(args.interval_seconds), 0.0)
    max_cycles = max(int(args.max_cycles), 0)

    if interval_seconds <= 0:
        try:
            summary = _purge_once()
        except Exception as exc:
            logger.exception("Operational retention cleanup failed")
            capture_exception(
                exc,
                tags={"worker": "operational-retention", "operation": "one_shot_purge"},
            )
            return 1
        print(json.dumps(summary, sort_keys=True))
        return 0

    logger.info(
        "Starting operational retention cleanup loop: interval_seconds=%s max_cycles=%s",
        interval_seconds,
        max_cycles or "infinite",
    )
    cycle = 0
    sleep_seconds = max(interval_seconds, 0.1)
    try:
        while True:
            try:
                summary = _purge_once()
            except Exception as exc:
                logger.exception("Operational retention cleanup cycle failed")
                capture_exception(
                    exc,
                    tags={"worker": "operational-retention", "operation": "loop_purge"},
                )
            else:
                logger.info(
                    "Operational retention cleanup summary: %s",
                    json.dumps(summary, sort_keys=True),
                )

            cycle += 1
            if max_cycles and cycle >= max_cycles:
                break

            time.sleep(sleep_seconds)
    except KeyboardInterrupt:
        logger.info("Stopping operational retention cleanup loop")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
