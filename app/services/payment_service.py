import time
import uuid
import json
import logging
from datetime import datetime, timedelta

from fastapi import HTTPException

from app.core.config import config

logger = logging.getLogger(__name__)


class PaymentService:
    """Payment service supporting YooKassa and Yandex Pay"""

    async def create_payment(self, user_id: int, plan: str, provider: str, db) -> dict:
        """Create a new payment"""
        if plan not in ("pro", "business"):
            raise HTTPException(400, "Invalid plan")
        
        if plan == "free":
            raise HTTPException(400, "Free plan does not require payment")
        
        amount = config.PLAN_PRICES.get(plan, 0)
        if amount <= 0:
            raise HTTPException(400, "Invalid plan price")
        
        now = time.time()
        payment_id = str(uuid.uuid4())
        
        # Create payment based on provider
        if provider == "yookassa":
            confirmation_url = await self._create_yookassa_payment(payment_id, plan, amount)
        elif provider == "yandex_pay":
            confirmation_url = await self._create_yandex_pay_payment(payment_id, plan, amount)
        else:
            raise HTTPException(400, "Unsupported payment provider")
        
        # Save payment to DB
        await db.execute(
            """INSERT INTO payments
            (user_id, payment_id, provider, plan, amount, currency, status, metadata, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                user_id, payment_id, provider, plan, amount, "RUB",
                "pending", json.dumps({"confirmation_url": confirmation_url}),
                now, now
            )
        )
        await db.commit()
        
        logger.info(f"Payment created: {payment_id} for user {user_id}, plan {plan}, provider {provider}")
        
        return {
            "id": None,
            "payment_id": payment_id,
            "provider": provider,
            "plan": plan,
            "amount": amount,
            "currency": "RUB",
            "status": "pending",
            "confirmation_url": confirmation_url,
            "created_at": datetime.fromtimestamp(now)
        }

    async def _create_yookassa_payment(self, payment_id: str, plan: str, amount: int) -> str:
        """Create payment via YooKassa"""
        if not config.yookassa_enabled:
            # Demo mode - return mock confirmation URL
            logger.warning("YooKassa not configured, using demo mode")
            return f"{config.APP_URL}/payment/demo?payment_id={payment_id}&provider=yookassa"
        
        try:
            from yookassa import Configuration, Payment as YooKassaPayment
            
            Configuration.account_id = config.YOOKASSA_SHOP_ID
            Configuration.secret_key = config.YOOKASSA_SECRET_KEY
            
            plan_features = config.PLAN_FEATURES.get(plan, {})
            payment = YooKassaPayment.create({
                "amount": {
                    "value": f"{amount}.00",
                    "currency": "RUB"
                },
                "confirmation": {
                    "type": "redirect",
                    "return_url": f"{config.APP_URL}/payment/success?payment_id={payment_id}"
                },
                "capture": True,
                "description": f"QNTX.Beacon - Тариф {plan_features.get('name', plan)}",
                "metadata": {
                    "payment_id": payment_id,
                    "plan": plan
                }
            }, payment_id)
            
            return payment.confirmation.confirmation_url
        except ImportError:
            logger.warning("yookassa library not installed, using demo mode")
            return f"{config.APP_URL}/payment/demo?payment_id={payment_id}&provider=yookassa"
        except Exception as e:
            logger.error(f"YooKassa payment creation failed: {e}")
            raise HTTPException(500, f"Payment creation failed: {str(e)}")

    async def _create_yandex_pay_payment(self, payment_id: str, plan: str, amount: int) -> str:
        """Create payment via Yandex Pay"""
        if not config.yandex_pay_enabled:
            logger.warning("Yandex Pay not configured, using demo mode")
            return f"{config.APP_URL}/payment/demo?payment_id={payment_id}&provider=yandex_pay"
        
        # Yandex Pay integration
        # In production, this would use the Yandex Pay API
        logger.info(f"Creating Yandex Pay payment: {payment_id}, amount: {amount}")
        return f"{config.APP_URL}/payment/demo?payment_id={payment_id}&provider=yandex_pay"

    async def handle_yookassa_webhook(self, event_data: dict, db) -> dict:
        """Handle YooKassa webhook notification"""
        try:
            event_type = event_data.get("event")
            payment_obj = event_data.get("object", {})
            
            metadata = payment_obj.get("metadata", {})
            payment_id = metadata.get("payment_id")
            
            if not payment_id:
                logger.warning("YooKassa webhook: no payment_id in metadata")
                return {"status": "ignored"}
            
            if event_type == "payment.succeeded":
                return await self._confirm_payment(payment_id, "completed", db)
            elif event_type == "payment.canceled":
                return await self._confirm_payment(payment_id, "canceled", db)
            
            return {"status": "ignored"}
        except Exception as e:
            logger.error(f"YooKassa webhook error: {e}")
            return {"status": "error", "message": str(e)}

    async def handle_yandex_pay_webhook(self, event_data: dict, db) -> dict:
        """Handle Yandex Pay webhook notification"""
        try:
            payment_id = event_data.get("payment_id")
            status = event_data.get("status")
            
            if not payment_id:
                return {"status": "ignored"}
            
            if status == "completed":
                return await self._confirm_payment(payment_id, "completed", db)
            elif status == "canceled":
                return await self._confirm_payment(payment_id, "canceled", db)
            
            return {"status": "ignored"}
        except Exception as e:
            logger.error(f"Yandex Pay webhook error: {e}")
            return {"status": "error", "message": str(e)}

    async def _confirm_payment(self, payment_id: str, status: str, db) -> dict:
        """Confirm payment and activate plan"""
        cur = await db.execute(
            "SELECT id, user_id, plan, status FROM payments WHERE payment_id = ?",
            (payment_id,)
        )
        row = await cur.fetchone()
        
        if not row:
            logger.warning(f"Payment not found: {payment_id}")
            return {"status": "not_found"}
        
        db_payment_id, user_id, plan, current_status = row
        
        if current_status == "completed":
            return {"status": "already_completed"}
        
        now = time.time()
        
        # Update payment status
        await db.execute(
            "UPDATE payments SET status = ?, updated_at = ? WHERE payment_id = ?",
            (status, now, payment_id)
        )
        
        if status == "completed":
            # Update user plan
            await db.execute(
                "UPDATE users SET plan = ?, updated_at = ? WHERE id = ?",
                (plan, now, user_id)
            )
            
            # Create/update subscription
            expires_at = now + 30 * 86400  # 30 days
            await db.execute(
                """INSERT INTO subscriptions
                (user_id, plan, status, payment_id, starts_at, expires_at, auto_renew, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?)""",
                (user_id, plan, "active", payment_id, now, expires_at, 0, now, now)
            )
            
            logger.info(f"Payment confirmed: {payment_id}, plan {plan} activated for user {user_id}")
        
        await db.commit()
        return {"status": status, "payment_id": payment_id, "plan": plan}

    async def confirm_demo_payment(self, payment_id: str, db) -> dict:
        """Confirm demo payment (for testing without real payment providers)"""
        return await self._confirm_payment(payment_id, "completed", db)

    async def get_payment_status(self, payment_id: str, db) -> dict:
        """Get payment status"""
        cur = await db.execute(
            "SELECT payment_id, status, plan, amount, created_at FROM payments WHERE payment_id = ?",
            (payment_id,)
        )
        row = await cur.fetchone()
        
        if not row:
            raise HTTPException(404, "Payment not found")
        
        return {
            "payment_id": row[0],
            "status": row[1],
            "plan": row[2],
            "amount": row[3]
        }

    async def get_user_payments(self, user_id: int, db) -> list:
        """Get user's payment history"""
        cur = await db.execute(
            "SELECT payment_id, provider, plan, amount, currency, status, created_at FROM payments WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        )
        rows = await cur.fetchall()
        
        return [
            {
                "payment_id": r[0],
                "provider": r[1],
                "plan": r[2],
                "amount": r[3],
                "currency": r[4],
                "status": r[5],
                "created_at": datetime.fromtimestamp(r[6])
            }
            for r in rows
        ]

    async def get_user_subscription(self, user_id: int, db) -> dict:
        """Get user's current subscription"""
        cur = await db.execute(
            """SELECT plan, status, starts_at, expires_at, auto_renew
            FROM subscriptions WHERE user_id = ? AND status = 'active'
            ORDER BY created_at DESC LIMIT 1""",
            (user_id,)
        )
        row = await cur.fetchone()
        
        if not row:
            return {"plan": "free", "status": "active", "auto_renew": False}
        
        plan, status, starts_at, expires_at, auto_renew = row
        
        # Check if subscription expired
        if expires_at and time.time() > expires_at:
            await db.execute(
                "UPDATE subscriptions SET status = 'expired' WHERE user_id = ? AND status = 'active' AND expires_at < ?",
                (user_id, time.time())
            )
            await db.execute("UPDATE users SET plan = 'free' WHERE id = ?", (user_id,))
            await db.commit()
            return {"plan": "free", "status": "expired", "auto_renew": False}
        
        return {
            "plan": plan,
            "status": status,
            "starts_at": datetime.fromtimestamp(starts_at),
            "expires_at": datetime.fromtimestamp(expires_at) if expires_at else None,
            "auto_renew": bool(auto_renew)
        }

    def get_available_plans(self) -> list:
        """Get all available plans with pricing"""
        plans = []
        for plan_id in ("free", "pro", "business"):
            features = config.PLAN_FEATURES.get(plan_id, {})
            plans.append({
                "id": plan_id,
                "name": features.get("name", plan_id),
                "price": config.PLAN_PRICES.get(plan_id, 0),
                **{k: v for k, v in features.items() if k != "name"}
            })
        return plans


payment_service = PaymentService()
