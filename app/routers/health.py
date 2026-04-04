import time
import logging

from fastapi import APIRouter, Request

from app.core.config import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["system"])

START_TIME = time.time()


@router.get("/health")
async def health_check(request: Request):
    """Health check endpoint for load balancers and monitoring"""
    checks = {}

    # Database check
    try:
        db = request.app.state.db
        await db.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # Redis check
    if config.redis_enabled:
        try:
            from app.core.rate_limiter import rate_limiter
            if rate_limiter and hasattr(rate_limiter, "_redis") and rate_limiter._redis:
                await rate_limiter._redis.ping()
                checks["redis"] = "ok"
            else:
                checks["redis"] = "not initialized"
        except Exception as e:
            checks["redis"] = f"error: {e}"
    else:
        checks["redis"] = "disabled"

    uptime = time.time() - START_TIME
    all_ok = all(v == "ok" or v == "disabled" for v in checks.values())

    return {
        "status": "healthy" if all_ok else "degraded",
        "version": "3.1.0",
        "uptime_seconds": round(uptime),
        "checks": checks,
    }


@router.get("/info")
async def app_info():
    """Public application info"""
    return {
        "name": config.APP_NAME,
        "version": "3.1.0",
        "features": {
            "email": config.email_enabled,
            "payments": config.yookassa_enabled or config.yandex_pay_enabled,
            "telegram": config.telegram_enabled,
        },
    }
