import logging
from typing import Dict, Optional

logger = logging.getLogger("app.metrics")


class MetricsService:
    """Simple metrics facade backed by structured logs."""

    @staticmethod
    def increment(name: str, value: int = 1, tags: Optional[Dict[str, str]] = None) -> None:
        logger.info(
            "metric.counter name=%s value=%s tags=%s",
            name,
            int(value),
            MetricsService._sanitize_tags(tags),
        )

    @staticmethod
    def histogram(name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
        logger.info(
            "metric.histogram name=%s value=%s tags=%s",
            name,
            float(value),
            MetricsService._sanitize_tags(tags),
        )

    @staticmethod
    def _sanitize_tags(tags: Optional[Dict[str, str]]) -> Dict[str, str]:
        if not tags:
            return {}
        clean: Dict[str, str] = {}
        for key, value in tags.items():
            if key is None or value is None:
                continue
            clean[str(key)] = str(value)
        return clean
