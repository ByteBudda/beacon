import time
import logging
import json

from fastapi import APIRouter, Request, Depends, HTTPException

from app.dependencies import get_current_user_id, require_admin
from app.core.security import validate_promocode

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/promocodes", tags=["promocodes"])


@router.post("/redeem")
async def redeem_promocode(data: dict, request: Request, user_id: int = Depends(get_current_user_id)):
    """Redeem a promocode to activate a plan"""
    code = validate_promocode(data.get("code", ""))
    if not code:
        raise HTTPException(400, "Promocode required")

    db = request.app.state.db
    now = time.time()

    cur = await db.execute(
        "SELECT id, plan, duration_days, max_uses, used_count, is_active, expires_at FROM promocodes WHERE code = ?",
        (code,)
    )
    row = await cur.fetchone()

    if not row:
        raise HTTPException(404, "Invalid promocode")

    pc_id, plan, duration, max_uses, used, is_active, expires = row

    if not is_active:
        raise HTTPException(400, "Promocode is deactivated")
    if expires > 0 and now > expires:
        raise HTTPException(400, "Promocode expired")
    if used >= max_uses:
        raise HTTPException(400, "Promocode usage limit reached")

    # Activate plan
    expires_at = now + duration * 86400
    await db.execute("UPDATE users SET plan = ?, updated_at = ? WHERE id = ?", (plan, now, user_id))
    await db.execute(
        "INSERT INTO subscriptions (user_id, plan, status, starts_at, expires_at, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
        (user_id, plan, "active", now, expires_at, now, now)
    )
    await db.execute("UPDATE promocodes SET used_count = used_count + 1 WHERE id = ?", (pc_id,))
    await db.commit()

    logger.info(f"User {user_id} redeemed promocode {code} for plan {plan}")
    return {"status": "ok", "plan": plan, "expires_days": duration}


# Admin endpoints

@router.get("")
async def list_promocodes(request: Request, admin: dict = Depends(require_admin)):
    """List all promocodes (admin)"""
    db = request.app.state.db
    cur = await db.execute(
        "SELECT id, code, plan, duration_days, max_uses, used_count, is_active, expires_at, created_at FROM promocodes ORDER BY created_at DESC"
    )
    rows = await cur.fetchall()
    return {
        "items": [
            {
                "id": r[0], "code": r[1], "plan": r[2], "duration_days": r[3],
                "max_uses": r[4], "used_count": r[5], "is_active": bool(r[6]),
                "expires_at": r[7], "created_at": r[8]
            }
            for r in rows
        ]
    }


@router.post("")
async def create_promocode(data: dict, request: Request, admin: dict = Depends(require_admin)):
    """Create promocode (admin)"""
    code = validate_promocode(data.get("code", ""))
    plan = data.get("plan", "pro")
    duration = data.get("duration_days", 30)
    max_uses = data.get("max_uses", 1)
    expires_hours = data.get("expires_hours", 0)

    if not code or len(code) < 4:
        raise HTTPException(400, "Code must be at least 4 chars")
    if plan not in ("pro", "business"):
        raise HTTPException(400, "Plan must be pro or business")

    db = request.app.state.db
    now = time.time()
    expires_at = now + expires_hours * 3600 if expires_hours > 0 else 0

    try:
        await db.execute(
            "INSERT INTO promocodes (code, plan, duration_days, max_uses, expires_at, created_at) VALUES (?,?,?,?,?,?)",
            (code, plan, duration, max_uses, expires_at, now)
        )
        await db.commit()
    except Exception:
        raise HTTPException(409, "Promocode already exists")

    logger.info(f"Admin created promocode: {code}")
    return {"status": "ok", "code": code}


@router.delete("/{pc_id}")
async def delete_promocode(pc_id: int, request: Request, admin: dict = Depends(require_admin)):
    """Delete promocode (admin)"""
    db = request.app.state.db
    await db.execute("DELETE FROM promocodes WHERE id = ?", (pc_id,))
    await db.commit()
    return {"status": "deleted"}
