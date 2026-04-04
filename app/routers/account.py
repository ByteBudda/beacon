import time
import logging

from fastapi import APIRouter, Request, Depends, HTTPException

from app.dependencies import get_current_user_id, get_current_user
from app.core.security import verify_password, hash_password, generate_api_key, hash_api_key

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/account", tags=["account"])


@router.get("")
async def get_account(request: Request, user_id: int = Depends(get_current_user_id)):
    """Get current user account details"""
    db = request.app.state.db
    cur = await db.execute(
        "SELECT id, username, email, plan, role, email_verified, is_active, api_key, created_at FROM users WHERE id = ?",
        (user_id,)
    )
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "User not found")

    cur = await db.execute("SELECT COUNT(*) FROM links WHERE user_id = ?", (user_id,))
    links = (await cur.fetchone())[0]
    cur = await db.execute("SELECT COALESCE(SUM(clicks), 0) FROM links WHERE user_id = ?", (user_id,))
    clicks = (await cur.fetchone())[0]

    # Subscription
    cur = await db.execute(
        "SELECT plan, status, expires_at FROM subscriptions WHERE user_id = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    )
    sub = await cur.fetchone()

    from app.core.config import config
    
    plan = row[3]
    plan_limit = config.PLAN_LIMITS.get(plan, 50)
    
    # Get referral count
    cur = await db.execute("SELECT referral_count FROM users WHERE id = ?", (user_id,))
    ref_row = await cur.fetchone()
    referral_count = ref_row[0] if ref_row else 0
    
    return {
        "id": row[0], "username": row[1], "email": row[2], "plan": plan,
        "role": row[4], "email_verified": bool(row[5]), "is_active": bool(row[6]),
        "has_api_key": bool(row[7]), "created_at": row[8], "api_key": row[7],
        "links_count": links, "total_clicks": clicks, "referral_count": referral_count,
        "plan_limit": plan_limit,
        "subscription": {"plan": sub[0], "status": sub[1], "expires_at": sub[2]} if sub else None,
    }


@router.put("/email")
async def change_email(data: dict, request: Request, user_id: int = Depends(get_current_user_id)):
    """Change email address"""
    new_email = data.get("new_email", "").strip().lower()
    password = data.get("password", "")

    if not new_email or not password:
        raise HTTPException(400, "new_email and password required")

    db = request.app.state.db
    cur = await db.execute("SELECT password_hash, email FROM users WHERE id = ?", (user_id,))
    row = await cur.fetchone()
    if not row or not verify_password(password, row[0]):
        raise HTTPException(401, "Invalid password")

    # Check if new email is taken
    cur = await db.execute("SELECT id FROM users WHERE email = ? AND id != ?", (new_email, user_id))
    if await cur.fetchone():
        raise HTTPException(409, "Email already in use")

    now = time.time()
    await db.execute(
        "UPDATE users SET email = ?, email_verified = 0, updated_at = ? WHERE id = ?",
        (new_email, now, user_id)
    )
    await db.commit()

    logger.info(f"User {user_id} changed email from {row[1]} to {new_email}")
    return {"status": "ok", "message": "Email changed. Please verify your new email."}


@router.post("/api-key")
async def generate_new_api_key(request: Request, user_id: int = Depends(get_current_user_id)):
    """Generate or regenerate API key"""
    db = request.app.state.db

    # Check plan allows API access
    cur = await db.execute("SELECT plan FROM users WHERE id = ?", (user_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "User not found")

    from app.core.config import config
    features = config.PLAN_FEATURES.get(row[0], {})
    if not features.get("api_access"):
        raise HTTPException(403, "API access requires Pro or Business plan")

    api_key = generate_api_key()
    hashed = hash_api_key(api_key)
    await db.execute("UPDATE users SET api_key = ?, updated_at = ? WHERE id = ?", (hashed, time.time(), user_id))
    await db.commit()

    return {"api_key": api_key, "message": "Save this key. It won't be shown again."}


@router.get("/api-key")
async def get_api_key(request: Request, user_id: int = Depends(get_current_user_id)):
    """Get current API key"""
    db = request.app.state.db
    cur = await db.execute("SELECT api_key IS NOT NULL FROM users WHERE id = ?", (user_id,))
    row = await cur.fetchone()
    return {"has_api_key": bool(row[0])}

@router.delete("/api-key")
async def revoke_api_key(request: Request, user_id: int = Depends(get_current_user_id)):
    """Revoke API key"""
    db = request.app.state.db
    await db.execute("UPDATE users SET api_key = NULL, updated_at = ? WHERE id = ?", (time.time(), user_id))
    await db.commit()
    return {"status": "ok"}


@router.delete("")
async def delete_account(data: dict, request: Request, user_id: int = Depends(get_current_user_id)):
    """Delete user account (GDPR)"""
    password = data.get("password", "")
    if not password:
        raise HTTPException(400, "Password required")

    db = request.app.state.db
    cur = await db.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
    row = await cur.fetchone()
    if not row or not verify_password(password, row[0]):
        raise HTTPException(401, "Invalid password")

    await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    await db.commit()

    logger.info(f"User {user_id} deleted their account")
    return {"status": "deleted"}
