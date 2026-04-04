import json
import logging

from fastapi import APIRouter, Request, Depends, HTTPException

from app.dependencies import get_current_user_id, get_current_user
from app.models.schemas import PaymentCreate
from app.services.payment_service import payment_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.get("/plans")
async def get_plans():
    """Get available plans with pricing"""
    return {"plans": payment_service.get_available_plans()}


@router.post("/trial")
async def start_trial(
    request: Request,
    user_id: int = Depends(get_current_user_id)
):
    """Start PRO trial (7 days)"""
    from app.services.trial_service import trial_service
    
    db = request.app.state.db
    result = await trial_service.start_trial(user_id, db)
    
    if "error" in result:
        raise HTTPException(400, result["error"])
    
    return result


@router.get("/trial/status")
async def check_trial(
    request: Request,
    user_id: int = Depends(get_current_user_id)
):
    """Check trial status"""
    from app.services.trial_service import trial_service
    
    db = request.app.state.db
    return await trial_service.check_trial(user_id, db)


@router.post("")
async def create_payment(
    data: PaymentCreate,
    request: Request,
    user_id: int = Depends(get_current_user_id)
):
    """Create a new payment for plan upgrade"""
    db = request.app.state.db
    result = await payment_service.create_payment(user_id, data.plan, data.provider, db)
    return result


@router.get("/{payment_id}")
async def get_payment_status(
    payment_id: str,
    request: Request,
    user_id: int = Depends(get_current_user_id)
):
    """Get payment status"""
    db = request.app.state.db
    return await payment_service.get_payment_status(payment_id, db)


@router.get("")
async def get_user_payments(request: Request, user_id: int = Depends(get_current_user_id)):
    """Get user's payment history"""
    db = request.app.state.db
    payments = await payment_service.get_user_payments(user_id, db)
    return {"payments": payments}


@router.get("/subscription/current")
async def get_current_subscription(request: Request, user_id: int = Depends(get_current_user_id)):
    """Get user's current subscription"""
    db = request.app.state.db
    return await payment_service.get_user_subscription(user_id, db)


@router.get("/demo/{payment_id}")
async def confirm_demo_payment(payment_id: str, request: Request):
    """Confirm demo payment (for testing)"""
    db = request.app.state.db
    return await payment_service.confirm_demo_payment(payment_id, db)


@router.post("/webhook/yookassa")
async def yookassa_webhook(request: Request):
    """YooKassa webhook endpoint"""
    signature = request.headers.get("X-YooKassa-Signature", "")
    if config.YOOKASSA_SECRET_KEY and signature != config.YOOKASSA_SECRET_KEY[:16]:
        if not config.DEBUG:
            logger.warning("YooKassa webhook: invalid signature")
            raise HTTPException(403, "Invalid signature")
    
    db = request.app.state.db
    try:
        body = await request.json()
        return await payment_service.handle_yookassa_webhook(body, db)
    except Exception as e:
        logger.error(f"YooKassa webhook error: {e}")
        return {"status": "error"}


@router.post("/webhook/yandex-pay")
async def yandex_pay_webhook(request: Request):
    """Yandex Pay webhook endpoint"""
    signature = request.headers.get("X-Yandex-Pay-Signature", "")
    if config.YANDEX_PAY_SECRET_KEY and signature != config.YANDEX_PAY_SECRET_KEY[:16]:
        if not config.DEBUG:
            logger.warning("Yandex Pay webhook: invalid signature")
            raise HTTPException(403, "Invalid signature")
    
    db = request.app.state.db
    try:
        body = await request.json()
        return await payment_service.handle_yandex_pay_webhook(body, db)
    except Exception as e:
        logger.error(f"Yandex Pay webhook error: {e}")
        return {"status": "error"}
