import logging
from typing import Any, Dict

import asyncio
import stripe
from time import perf_counter
from fastapi import APIRouter, HTTPException, Request, status

from app.core.config import settings
from app.services.metrics_service import MetricsService
from app.services.stripe_webhook_inbox_service import StripeWebhookInboxService
from app.services.subscription_service import (
    StripeWebhookNonRetryableError,
    StripeWebhookProcessingError,
    SubscriptionService,
)

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
    if not SubscriptionService.is_stripe_event_livemode_allowed(
        event=event,
        source="http_ingress",
    ):
        return {"status": "ignored"}

    if settings.STRIPE_WEBHOOK_FAST_ACK_ENABLED:
        ack_started_at = perf_counter()
        try:
            enqueued = await asyncio.to_thread(
                StripeWebhookInboxService.enqueue_event_threadsafe,
                event=event,
            )
        except StripeWebhookProcessingError as exc:
            logger.error(
                "Stripe webhook inbox enqueue failed: type=%s id=%s error=%s",
                event.get("type"),
                event.get("id"),
                exc,
            )
            MetricsService.increment(
                "purchase_webhook_retry_total",
                tags={
                    "event_type": event_type,
                    "stage": "enqueue",
                },
            )
            raise HTTPException(status_code=500, detail="Webhook processing failed")
        except Exception as exc:
            logger.exception(
                "Unexpected Stripe webhook inbox enqueue failure: type=%s id=%s error=%s",
                event.get("type"),
                event.get("id"),
                exc,
            )
            MetricsService.increment(
                "purchase_webhook_failed_total",
                tags={
                    "event_type": event_type,
                    "stage": "enqueue",
                },
            )
            raise HTTPException(status_code=500, detail="Webhook processing failed")

        elapsed_ms = (perf_counter() - ack_started_at) * 1000.0
        MetricsService.increment(
            "purchase_webhook_ingested_total",
            tags={
                "event_type": event_type,
                "enqueued": "true" if enqueued else "false",
            },
        )
        MetricsService.histogram(
            "purchase_webhook_ack_latency_ms",
            elapsed_ms,
            tags={
                "event_type": event_type,
                "processing_mode": "fast_ack",
            },
        )
        return {"status": "ok"}

    started_at = perf_counter()
    try:
        await asyncio.to_thread(
            SubscriptionService.handle_webhook_event_threadsafe,
            event=event,
        )
    except StripeWebhookNonRetryableError as exc:
        logger.warning(
            "Stripe webhook non-retryable event acknowledged: type=%s id=%s reason=%s",
            event.get("type"),
            event.get("id"),
            exc.reason,
        )
        MetricsService.increment(
            "purchase_webhook_acknowledged_non_retryable_total",
            tags={
                "event_type": event_type,
                "reason": exc.reason,
            },
        )
        return {"status": "ok"}
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
