import logging
from datetime import datetime

from fastapi import APIRouter, Request, Depends, HTTPException, Query

from app.dependencies import require_admin
from app.models.schemas import AdminUserUpdate
from app.services.admin_service import admin_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/stats")
async def get_dashboard_stats(request: Request, admin: dict = Depends(require_admin)):
    """Get admin dashboard statistics"""
    db = request.app.state.db
    return await admin_service.get_dashboard_stats(db)


@router.get("/users")
async def list_users(
    request: Request,
    admin: dict = Depends(require_admin),
    page: int = 1,
    limit: int = 50,
    search: str = "",
    plan: str = "",
    role: str = ""
):
    """List all users"""
    db = request.app.state.db
    return await admin_service.list_users(db, page, limit, search, plan, role)


@router.get("/users/{user_id}")
async def get_user(user_id: int, request: Request, admin: dict = Depends(require_admin)):
    """Get user details"""
    db = request.app.state.db
    cur = await db.execute(
        "SELECT id, username, email, plan, role, email_verified, is_active, created_at FROM users WHERE id = ?",
        (user_id,)
    )
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "User not found")
    
    cur = await db.execute("SELECT COUNT(*) FROM links WHERE user_id = ?", (user_id,))
    links_count = (await cur.fetchone())[0]
    
    cur = await db.execute("SELECT COALESCE(SUM(clicks), 0) FROM links WHERE user_id = ?", (user_id,))
    total_clicks = (await cur.fetchone())[0] or 0
    
    # Get referrer info
    cur = await db.execute(
        "SELECT username, email FROM users WHERE id = (SELECT referral_parent FROM users WHERE id = ?)",
        (user_id,)
    )
    referrer_row = await cur.fetchone()
    referrer = {"username": referrer_row[0], "email": referrer_row[1]} if referrer_row else None
    
    # Get subscription
    cur = await db.execute(
        "SELECT plan, status, expires_at FROM subscriptions WHERE user_id = ? AND status IN ('active', 'canceled') ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    )
    sub_row = await cur.fetchone()
    subscription = {"plan": sub_row[0], "status": sub_row[1], "expires_at": sub_row[2]} if sub_row else None
    
    return {
        "id": row[0],
        "username": row[1],
        "email": row[2],
        "plan": row[3],
        "role": row[4],
        "referrer": referrer,
        "subscription": subscription,
        "email_verified": bool(row[5]),
        "is_active": bool(row[6]),
        "created_at": datetime.fromtimestamp(row[7]) if row[7] else None,
        "links_count": links_count,
        "total_clicks": total_clicks
    }


@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    data: AdminUserUpdate,
    request: Request,
    admin: dict = Depends(require_admin)
):
    """Update user (plan, role, active status)"""
    db = request.app.state.db
    return await admin_service.update_user(user_id, data.dict(exclude_unset=True), db)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: int,
    request: Request,
    admin: dict = Depends(require_admin)
):
    """Delete user"""
    db = request.app.state.db
    return await admin_service.delete_user(user_id, admin["id"], db)


@router.get("/users/{user_id}/referrals")
async def get_user_referrals(
    user_id: int,
    request: Request,
    admin: dict = Depends(require_admin)
):
    """Get user's referrals"""
    db = request.app.state.db
    
    cur = await db.execute(
        "SELECT id, username, email, plan, created_at FROM users WHERE referral_parent = ? ORDER BY created_at DESC",
        (user_id,)
    )
    rows = await cur.fetchall()
    
    return {
        "referrals": [
            {"id": r[0], "username": r[1], "email": r[2], "plan": r[3], "created_at": r[4]}
            for r in rows
        ],
        "total": len(rows)
    }


@router.get("/payments")
async def list_payments(
    request: Request,
    admin: dict = Depends(require_admin),
    page: int = 1,
    limit: int = 50,
    status: str = ""
):
    """List all payments"""
    db = request.app.state.db
    return await admin_service.list_all_payments(db, page, limit, status)


# ========== LINK MODERATION ==========

@router.get("/links/moderation")
async def list_flagged_links(
    request: Request,
    admin: dict = Depends(require_admin),
    page: int = 1,
    limit: int = 50,
    status: str = "",
    mod_status: str = ""
):
    """List links for moderation. Filter by moderation_status: blacklisted, phishing, malware, suspicious, pending, ok."""
    db = request.app.state.db
    offset = (page - 1) * limit

    conditions = []
    params = []

    if mod_status:
        conditions.append("l.moderation_status = ?")
        params.append(mod_status)
    elif status == "flagged":
        conditions.append("l.moderation_status NOT IN ('ok', 'pending')")
    elif status == "banned":
        conditions.append("l.is_active = 0")
    elif status == "pending":
        conditions.append("l.moderation_status = 'pending'")

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    cur = await db.execute(f"SELECT COUNT(*) FROM links l {where}", params)
    total = (await cur.fetchone())[0]

    cur = await db.execute(
        f"""SELECT l.id, l.slug, l.url, l.title, l.moderation_status, l.moderation_reason,
                l.is_active, l.clicks, l.created_at, u.username
            FROM links l JOIN users u ON l.user_id = u.id
            {where}
            ORDER BY l.created_at DESC LIMIT ? OFFSET ?""",
        (*params, limit, offset)
    )
    rows = await cur.fetchall()

    return {
        "items": [
            {
                "id": r[0], "slug": r[1], "url": r[2], "title": r[3],
                "moderation_status": r[4], "moderation_reason": r[5],
                "is_active": bool(r[6]), "clicks": r[7],
                "created_at": r[8], "username": r[9]
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "limit": limit,
    }


@router.put("/links/{link_id}/ban")
async def ban_link(link_id: int, data: dict, request: Request, admin: dict = Depends(require_admin)):
    """Ban a link"""
    reason = data.get("reason", "Banned by admin")
    db = request.app.state.db

    cur = await db.execute("SELECT id, slug FROM links WHERE id = ?", (link_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Link not found")

    import time
    await db.execute(
        "UPDATE links SET is_active = 0, moderation_status = 'banned', moderation_reason = ? WHERE id = ?",
        (reason, link_id)
    )
    await db.commit()

    logger.info(f"Admin banned link {row[1]} (id={link_id}): {reason}")
    return {"status": "banned", "link_id": link_id}


@router.put("/links/{link_id}/unban")
async def unban_link(link_id: int, request: Request, admin: dict = Depends(require_admin)):
    """Unban a link"""
    db = request.app.state.db

    cur = await db.execute("SELECT id, slug FROM links WHERE id = ?", (link_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Link not found")

    await db.execute(
        "UPDATE links SET is_active = 1, moderation_status = 'ok', moderation_reason = '' WHERE id = ?",
        (link_id,)
    )
    await db.commit()

    logger.info(f"Admin unbanned link {row[1]} (id={link_id})")
    return {"status": "unbanned", "link_id": link_id}


@router.post("/links/{link_id}/recheck")
async def recheck_link(link_id: int, request: Request, admin: dict = Depends(require_admin)):
    """Re-check link for threats"""
    from app.services.link_checker import check_url

    db = request.app.state.db
    cur = await db.execute("SELECT id, slug, url FROM links WHERE id = ?", (link_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Link not found")

    _, slug, url = row
    result = await check_url(url)

    if not result["safe"]:
        await db.execute(
            "UPDATE links SET moderation_status = ?, moderation_reason = ?, is_active = 0 WHERE id = ?",
            (result["status"], result["reason"], link_id)
        )
    else:
        await db.execute(
            "UPDATE links SET moderation_status = 'ok', moderation_reason = '', is_active = 1 WHERE id = ?",
            (link_id,)
        )
    await db.commit()

    return {
        "link_id": link_id,
        "slug": slug,
        "result": result,
    }


# ========== EXPORT ==========

@router.get("/export/users")
async def export_users(request: Request, admin: dict = Depends(require_admin)):
    """Export all users as CSV"""
    from fastapi.responses import StreamingResponse
    import csv
    import io
    import time
    
    db = request.app.state.db
    cur = await db.execute(
        "SELECT id, username, email, plan, role, email_verified, is_active, created_at FROM users ORDER BY created_at DESC"
    )
    rows = await cur.fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "username", "email", "plan", "role", "email_verified", "is_active", "created_at"])
    for r in rows:
        writer.writerow([r[0], r[1], r[2], r[3], r[4], bool(r[5]), bool(r[6]), time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r[7]))])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=beacon_users.csv"}
    )


@router.get("/export/links")
async def export_links(request: Request, admin: dict = Depends(require_admin)):
    """Export all links as CSV"""
    from fastapi.responses import StreamingResponse
    import csv
    import io
    import time
    
    db = request.app.state.db
    cur = await db.execute(
        "SELECT l.id, l.slug, l.url, l.title, l.clicks, l.moderation_status, l.created_at, u.username FROM links l JOIN users u ON l.user_id = u.id ORDER BY l.created_at DESC"
    )
    rows = await cur.fetchall()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "slug", "url", "title", "clicks", "moderation_status", "created_at", "username"])
    for r in rows:
        writer.writerow([r[0], r[1], r[2], r[3], r[4], r[5], time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r[6])), r[7]])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=beacon_links.csv"}
    )


# ========== SYSTEM ==========

@router.get("/system")
async def get_system_info(request: Request, admin: dict = Depends(require_admin)):
    """Get system information"""
    db = request.app.state.db
    
    cur = await db.execute("SELECT COUNT(*) FROM users")
    total_users = (await cur.fetchone())[0]
    
    cur = await db.execute("SELECT COUNT(*) FROM links")
    total_links = (await cur.fetchone())[0]
    
    cur = await db.execute("SELECT COUNT(*) FROM clicks")
    total_clicks = (await cur.fetchone())[0]
    
    from app.core.config import config
    return {
        "version": "3.1.0",
        "database": "sqlite",
        "total_users": total_users,
        "total_links": total_links,
        "total_clicks": total_clicks,
        "jwt_expiration_hours": config.JWT_EXPIRATION_HOURS,
        "moderation_enabled": config.MODERATION_ENABLED,
        "telegram_enabled": config.telegram_enabled,
    }


@router.post("/cleanup")
async def cleanup_database(request: Request, admin: dict = Depends(require_admin)):
    """Cleanup expired links and old clicks"""
    import time
    db = request.app.state.db
    
    now = time.time()
    
    cur = await db.execute("SELECT COUNT(*) FROM links WHERE expires_at > 0 AND expires_at < ?", (now,))
    expired_count = (await cur.fetchone())[0]
    
    if expired_count > 0:
        cur = await db.execute("DELETE FROM links WHERE expires_at > 0 AND expires_at < ?", (now,))
    
    cur = await db.execute("SELECT COUNT(*) FROM clicks WHERE ts < ?", (now - 90 * 86400))
    old_clicks = (await cur.fetchone())[0]
    
    if old_clicks > 0:
        cur = await db.execute("DELETE FROM clicks WHERE ts < ?", (now - 90 * 86400))
    
    await db.commit()
    
    logger.info(f"Cleanup: {expired_count} links, {old_clicks} clicks removed")
    return {"status": "ok", "expired_links": expired_count, "old_clicks": old_clicks}


# ========== SETTINGS ==========

@router.get("/settings")
async def get_settings(request: Request, admin: dict = Depends(require_admin)):
    """Get all settings"""
    from app.core.config import config
    
    settings = {}
    for key in dir(config):
        if key.startswith('_'):
            continue
        val = getattr(config, key, None)
        if callable(val):
            continue
        if isinstance(val, dict):
            settings[key] = str(val)
        else:
            settings[key] = val
    
    db = request.app.state.db
    cur = await db.execute("SELECT key, value FROM settings")
    rows = await cur.fetchall()
    overrides = {r[0]: r[1] for r in rows}
    
    return {
        "defaults": settings,
        "overrides": overrides
    }


@router.put("/settings")
async def update_settings(data: dict, request: Request, admin: dict = Depends(require_admin)):
    """Update settings"""
    import time
    db = request.app.state.db
    now = time.time()
    
    for key, value in data.items():
        if value is None or value == "":
            await db.execute("DELETE FROM settings WHERE key = ?", (key,))
        else:
            await db.execute(
                "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                (key, str(value), now)
            )
    
    await db.commit()
    logger.info(f"Admin {admin['username']} updated settings: {list(data.keys())}")
    return {"status": "ok", "updated": list(data.keys())}


@router.get("/settings/ads")
async def get_ad_settings(request: Request, admin: dict = Depends(require_admin)):
    """Get ad settings"""
    db = request.app.state.db
    from app.services.ad_service import ad_service
    
    return {
        "ad_enabled": await ad_service.get(db, "ad_enabled", "false"),
        "ad_html": await ad_service.get(db, "ad_html", ""),
        "ad_delay": await ad_service.get(db, "ad_delay", "5"),
        "ad_title": await ad_service.get(db, "ad_title", "Подождите..."),
        "ad_skip_text": await ad_service.get(db, "ad_skip_text", "Перейти к ссылке"),
    }


@router.put("/settings/ads")
async def update_ad_settings(data: dict, request: Request, admin: dict = Depends(require_admin)):
    """Update ad settings"""
    import time
    db = request.app.state.db
    now = time.time()
    
    from app.services.ad_service import ad_service
    
    for key in ["ad_enabled", "ad_html", "ad_delay", "ad_title", "ad_skip_text"]:
        value = data.get(key, "")
        await db.execute(
            "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
            (key, str(value), now)
        )
    
    await db.commit()
    logger.info(f"Admin {admin['username']} updated ad settings")
    return {"status": "ok"}


# ========== SUBSCRIPTIONS ==========

@router.post("/users/{user_id}/subscribe")
async def create_user_subscription(
    user_id: int,
    data: dict,
    request: Request,
    admin: dict = Depends(require_admin)
):
    """Create and activate subscription for user"""
    plan = data.get("plan", "pro")
    if plan not in ("pro", "business"):
        raise HTTPException(400, "Invalid plan")
    
    import time
    db = request.app.state.db
    now = time.time()
    
    # Get plan duration
    plans = {
        "pro": 30,
        "business": 30
    }
    duration_days = plans.get(plan, 30)
    expires_at = now + duration_days * 86400
    
    # Update user plan
    await db.execute("UPDATE users SET plan = ?, updated_at = ? WHERE id = ?", (plan, now, user_id))
    
    # Create or update subscription
    await db.execute(
        """INSERT OR REPLACE INTO subscriptions 
           (user_id, plan, status, starts_at, expires_at, created_at, updated_at) 
           VALUES (?,?,?,?,?,?,?)""",
        (user_id, plan, "active", now, expires_at, now, now)
    )
    await db.commit()
    
    logger.info(f"Admin created subscription for user {user_id}: {plan}")
    return {"status": "ok", "plan": plan, "expires_at": expires_at}


@router.post("/users/{user_id}/extend")
async def extend_user_subscription(
    user_id: int,
    data: dict,
    request: Request,
    admin: dict = Depends(require_admin)
):
    """Extend user's subscription and optionally set plan"""
    days = data.get("days", 30)
    plan = data.get("plan", "pro")  # Default to pro
    
    if days < 1 or days > 365:
        raise HTTPException(400, "Invalid days")
    
    import time
    db = request.app.state.db
    now = time.time()
    
    # Update user's plan
    await db.execute("UPDATE users SET plan = ?, updated_at = ? WHERE id = ?", (plan, now, user_id))
    
    # Get current subscription
    cur = await db.execute(
        "SELECT id, expires_at FROM subscriptions WHERE user_id = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1",
        (user_id,)
    )
    row = await cur.fetchone()
    
    if row:
        # Update existing
        current_expires = row[1] if row[1] else now
        new_expires = max(current_expires, now) + days * 86400
        await db.execute(
            "UPDATE subscriptions SET plan = ?, expires_at = ?, updated_at = ? WHERE user_id = ? AND status = 'active'",
            (plan, new_expires, now, user_id)
        )
    else:
        # Create new subscription
        new_expires = now + days * 86400
        await db.execute(
            "INSERT INTO subscriptions (user_id, plan, status, starts_at, expires_at, auto_renew, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
            (user_id, plan, "active", now, new_expires, 0, now, now)
        )
    
    await db.commit()
    
    logger.info(f"Admin extended subscription for user {user_id} by {days} days, plan: {plan}")
    return {"status": "ok", "new_expires_at": new_expires}


@router.post("/users/{user_id}/cancel")
async def cancel_user_subscription(
    user_id: int,
    request: Request,
    admin: dict = Depends(require_admin)
):
    """Cancel user's subscription (keeps active until expiration)"""
    import time
    db = request.app.state.db
    now = time.time()
    
    # Mark as canceled but keep until expiration
    await db.execute(
        "UPDATE subscriptions SET status = 'canceled', updated_at = ? WHERE user_id = ? AND status = 'active'",
        (now, user_id)
    )
    await db.commit()
    
    logger.info(f"Admin canceled subscription for user {user_id}")
    return {"status": "ok", "message": "Subscription canceled, remains active until expiration"}
