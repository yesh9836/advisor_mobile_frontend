import logging
from typing import Any, Dict

import asyncio
import stripe
from time import perf_counter
from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import settings
from app.services.metrics_service import MetricsService
from app.services.subscription_service import StripeWebhookProcessingError, SubscriptionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post(
    "/stripe",
    status_code=status.HTTP_200_OK,
    summary="Stripe webhook endpoint",
)
async def stripe_webhook(
    request: Request,
) -> Dict[str, Any]:
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        logger.warning("Stripe webhook missing signature header")
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
    except ValueError:
        logger.warning("Stripe webhook payload invalid")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        logger.warning("Stripe webhook signature verification failed")
        raise HTTPException(status_code=400, detail="Invalid signature")

    logger.info(f"Stripe webhook verified: type={event.get('type')} id={event.get('id')}")
    event_type = str(event.get("type") or "unknown")
    started_at = perf_counter()
    try:
        await asyncio.to_thread(
            SubscriptionService.handle_webhook_event_threadsafe,
            event=event,
        )
    except StripeWebhookProcessingError as exc:
        logger.error(
            "Stripe webhook processing failed: type=%s id=%s error=%s",
            event.get("type"),
            event.get("id"),
            exc,
        )
        MetricsService.increment(
            "purchase_webhook_retry_total",
            tags={
                "event_type": event_type,
            },
        )
        raise HTTPException(status_code=500, detail="Webhook processing failed")
    except Exception as exc:
        logger.exception(
            "Unexpected Stripe webhook processing failure: type=%s id=%s error=%s",
            event.get("type"),
            event.get("id"),
            exc,
        )
        MetricsService.increment(
            "purchase_webhook_failed_total",
            tags={
                "event_type": event_type,
            },
        )
        raise HTTPException(status_code=500, detail="Webhook processing failed")

    elapsed_ms = (perf_counter() - started_at) * 1000.0
    MetricsService.increment(
        "purchase_webhook_processed_total",
        tags={
            "event_type": event_type,
        },
    )
    MetricsService.histogram(
        "purchase_webhook_processing_latency_ms",
        elapsed_ms,
        tags={
            "event_type": event_type,
        },
    )

    return {"status": "ok"}
