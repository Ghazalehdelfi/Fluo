"""Stripe billing routes: /api/billing/*."""

import os
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

import stripe

from database import User, UsageLog, SessionLocal
from auth import get_current_user
from dependencies import get_db
from agents.logging_utils import Colors, get_logger

logger = get_logger(__name__)
router = APIRouter()

# Module-level Stripe config (loaded after load_secrets() is called in main.py)
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

CREDIT_PACKS = {
    "5": {"amount_cents": 500, "credits": 100},  # $5  = 100 credits
    "10": {"amount_cents": 1000, "credits": 200},  # $10 = 200 credits
    "20": {"amount_cents": 2000, "credits": 400},  # $20 = 400 credits
}


def _get_or_create_stripe_customer(user: User, db: Session) -> str:
    """Return the Stripe Customer ID for *user*, creating one if needed."""
    if user.stripe_customer_id:
        return user.stripe_customer_id

    customer = stripe.Customer.create(
        email=user.email,
        metadata={"user_id": str(user.id)},
    )
    user.stripe_customer_id = customer.id
    db.commit()
    logger.info(f"Stripe: created customer {customer.id} for {user.email}")
    return customer.id


class CheckoutRequest(BaseModel):
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None
    pack: str = "20"  # "5", "10", or "20"


@router.post("/api/billing/create-checkout-session")
async def create_checkout_session(
    body: CheckoutRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe Checkout Session for a one-time credit pack payment."""
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe is not configured")

    pack = CREDIT_PACKS.get(body.pack)
    if not pack:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid pack. Choose one of: {', '.join(CREDIT_PACKS)}",
        )

    try:
        customer_id = _get_or_create_stripe_customer(user, db)

        origin = str(request.base_url).rstrip("/")
        success = body.success_url or f"{origin}/?purchase=success"
        cancel = body.cancel_url or f"{origin}/?purchase=cancel"

        session = stripe.checkout.Session.create(
            customer=customer_id,
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": pack["amount_cents"],
                        "product_data": {"name": f"Fluō Credit Pack — ${body.pack}"},
                    },
                    "quantity": 1,
                }
            ],
            mode="payment",
            success_url=success,
            cancel_url=cancel,
            client_reference_id=str(user.id),
            metadata={
                "user_id": str(user.id),
                "credits": str(pack["credits"]),
            },
        )
        return {"checkout_url": session.url}
    except stripe.StripeError as e:
        logger.error(f"Stripe error: {e}")
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Checkout error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/billing/webhook")
async def handle_stripe_webhook(request: Request):
    """Handle Stripe webhook events (checkout.session.completed → credit user)."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    if not webhook_secret:
        raise HTTPException(status_code=500, detail="Webhook secret not configured")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    if event["type"] == "checkout.session.completed":
        session_data = event["data"]["object"]
        client_ref = session_data.get("client_reference_id")
        metadata = session_data.get("metadata", {})
        credits_to_add = float(metadata.get("credits", "100"))

        if not client_ref:
            logger.warning(
                "Webhook: checkout.session.completed without client_reference_id"
            )
            return {"status": "ignored"}

        user_id = int(client_ref)
        db = SessionLocal()
        try:
            user_obj = db.query(User).filter(User.id == user_id).first()
            if user_obj:
                user_obj.credits_balance += credits_to_add
                stripe_customer = session_data.get("customer")
                if stripe_customer and not user_obj.stripe_customer_id:
                    user_obj.stripe_customer_id = stripe_customer
                db.commit()
                logger.info(
                    f"{Colors.GREEN}💳 Added {credits_to_add:.0f} credits to "
                    f"{user_obj.email} (balance: {user_obj.credits_balance:.0f}){Colors.END}"
                )
            else:
                logger.warning(f"Webhook: user {user_id} not found")
        finally:
            db.close()

    return {"status": "ok"}


@router.get("/api/billing/usage")
async def get_usage_history(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's API usage history."""
    logs = (
        db.query(UsageLog)
        .filter(UsageLog.user_id == user.id)
        .order_by(UsageLog.created_at.desc())
        .limit(100)
        .all()
    )
    total_spent = sum(log.cost_usd for log in logs)
    return {
        "credits_balance": user.credits_balance,
        "total_api_cost": round(total_spent, 4),
        "recent_usage": [
            {
                "model": log.model,
                "input_tokens": log.input_tokens,
                "output_tokens": log.output_tokens,
                "cost_usd": log.cost_usd,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs[:20]
        ],
    }
