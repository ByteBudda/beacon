import time
import logging
from datetime import datetime

from fastapi import HTTPException

from app.core.config import config
from app.core.security import hash_password

logger = logging.getLogger(__name__)


class AdminService:
    """Admin panel service"""

    async def get_dashboard_stats(self, db) -> dict:
        """Get admin dashboard statistics"""
        # Total users
        cur = await db.execute("SELECT COUNT(*) FROM users")
        total_users = (await cur.fetchone())[0]
        
        # Active users (verified email)
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE email_verified = 1")
        active_users = (await cur.fetchone())[0]
        
        # Total links
        cur = await db.execute("SELECT COUNT(*) FROM links")
        total_links = (await cur.fetchone())[0]
        
        # Total clicks
        cur = await db.execute("SELECT SUM(clicks) FROM links")
        row = await cur.fetchone()
        total_clicks = row[0] if row and row[0] else 0
        
        # Users by plan
        cur = await db.execute("SELECT plan, COUNT(*) FROM users GROUP BY plan")
        rows = await cur.fetchall()
        users_by_plan = {r[0]: r[1] for r in rows}
        
        # Recent payments
        cur = await db.execute(
            """SELECT p.payment_id, p.provider, p.plan, p.amount, p.status, p.created_at, u.username
            FROM payments p JOIN users u ON p.user_id = u.id
            ORDER BY p.created_at DESC LIMIT 10"""
        )
        rows = await cur.fetchall()
        recent_payments = [
            {
                "payment_id": r[0],
                "provider": r[1],
                "plan": r[2],
                "amount": r[3],
                "status": r[4],
                "created_at": datetime.fromtimestamp(r[5]),
                "username": r[6]
            }
            for r in rows
        ]
        
        # Recent users
        cur = await db.execute(
            "SELECT id, username, email, plan, email_verified, created_at FROM users ORDER BY created_at DESC LIMIT 10"
        )
        rows = await cur.fetchall()
        recent_users = [
            {
                "id": r[0],
                "username": r[1],
                "email": r[2],
                "plan": r[3],
                "email_verified": bool(r[4]),
                "created_at": datetime.fromtimestamp(r[5])
            }
            for r in rows
        ]
        
        # Links created today
        today_start = time.time() - (time.time() % 86400)
        cur = await db.execute("SELECT COUNT(*) FROM links WHERE created_at >= ?", (today_start,))
        links_today = (await cur.fetchone())[0]
        
        # Clicks today
        cur = await db.execute("SELECT COUNT(*) FROM clicks WHERE ts >= ?", (today_start,))
        clicks_today = (await cur.fetchone())[0]

        # Moderation stats
        cur = await db.execute("SELECT COUNT(*) FROM links WHERE moderation_status NOT IN ('ok', 'pending', '')")
        flagged_links = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM links WHERE is_active = 0 AND moderation_status NOT IN ('ok', 'pending', '')")
        banned_links = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM links WHERE moderation_status = 'pending'")
        pending_links = (await cur.fetchone())[0]

        return {
            "total_users": total_users,
            "active_users": active_users,
            "total_links": total_links,
            "total_clicks": total_clicks,
            "users_by_plan": users_by_plan,
            "recent_payments": recent_payments,
            "recent_users": recent_users,
            "links_today": links_today,
            "clicks_today": clicks_today,
            "flagged_links": flagged_links,
            "banned_links": banned_links,
            "pending_links": pending_links,
        }

    async def list_users(self, db, page: int = 1, limit: int = 50, search: str = "", plan: str = "", role: str = "") -> dict:
        """List all users with pagination and filters"""
        offset = (page - 1) * limit
        
        conditions = []
        params = []
        
        if search:
            conditions.append("(username LIKE ? OR email LIKE ?)")
            params.extend([f"%{search}%", f"%{search}%"])
        
        if plan:
            conditions.append("plan = ?")
            params.append(plan)
        
        if role:
            conditions.append("role = ?")
            params.append(role)
        
        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        
        # Get total count
        cur = await db.execute(f"SELECT COUNT(*) FROM users {where_clause}", params)
        total = (await cur.fetchone())[0]
        
        # Get users
        cur = await db.execute(
            f"""SELECT u.id, u.username, u.email, u.plan, u.role, u.email_verified, u.is_active, u.created_at,
                (SELECT COUNT(*) FROM links WHERE user_id = u.id) as links_count,
                (SELECT COALESCE(SUM(clicks), 0) FROM links WHERE user_id = u.id) as total_clicks
            FROM users u {where_clause}
            ORDER BY u.created_at DESC LIMIT ? OFFSET ?""",
            (*params, limit, offset)
        )
        rows = await cur.fetchall()
        
        users = [
            {
                "id": r[0],
                "username": r[1],
                "email": r[2],
                "plan": r[3],
                "role": r[4],
                "email_verified": bool(r[5]),
                "is_active": bool(r[6]),
                "created_at": datetime.fromtimestamp(r[7]),
                "links_count": r[8],
                "total_clicks": r[9]
            }
            for r in rows
        ]
        
        return {
            "items": users,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }

    async def get_user(self, user_id: int, db) -> dict:
        """Get user details"""
        cur = await db.execute(
            """SELECT u.id, u.username, u.email, u.plan, u.role, u.email_verified, u.is_active, u.created_at,
                (SELECT COUNT(*) FROM links WHERE user_id = u.id) as links_count,
                (SELECT COALESCE(SUM(clicks), 0) FROM links WHERE user_id = u.id) as total_clicks
            FROM users u WHERE u.id = ?""",
            (user_id,)
        )
        row = await cur.fetchone()
        
        if not row:
            raise HTTPException(404, "User not found")
        
        # Get subscription info
        cur = await db.execute(
            "SELECT plan, status, expires_at FROM subscriptions WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
            (user_id,)
        )
        sub_row = await cur.fetchone()
        subscription = None
        if sub_row:
            subscription = {
                "plan": sub_row[0],
                "status": sub_row[1],
                "expires_at": datetime.fromtimestamp(sub_row[2]) if sub_row[2] else None
            }
        
        # Get recent payments
        cur = await db.execute(
            "SELECT payment_id, provider, plan, amount, status, created_at FROM payments WHERE user_id = ? ORDER BY created_at DESC LIMIT 5",
            (user_id,)
        )
        payments = [
            {
                "payment_id": r[0],
                "provider": r[1],
                "plan": r[2],
                "amount": r[3],
                "status": r[4],
                "created_at": datetime.fromtimestamp(r[5])
            }
            for r in await cur.fetchall()
        ]
        
        return {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "plan": row[3],
            "role": row[4],
            "email_verified": bool(row[5]),
            "is_active": bool(row[6]),
            "created_at": datetime.fromtimestamp(row[7]),
            "links_count": row[8],
            "total_clicks": row[9],
            "subscription": subscription,
            "recent_payments": payments
        }

    async def update_user(self, user_id: int, data: dict, db) -> dict:
        """Update user (admin)"""
        cur = await db.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not await cur.fetchone():
            raise HTTPException(404, "User not found")
        
        updates = {}
        for field in ("plan", "role", "is_active"):
            if data.get(field) is not None:
                updates[field] = data[field]
        
        if updates:
            updates["updated_at"] = time.time()
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            await db.execute(f"UPDATE users SET {set_clause} WHERE id = ?", (*updates.values(), user_id))
            await db.commit()
        
        logger.info(f"Admin updated user {user_id}: {updates}")
        return await self.get_user(user_id, db)

    async def delete_user(self, user_id: int, admin_id: int, db) -> dict:
        """Delete user (admin)"""
        if user_id == admin_id:
            raise HTTPException(400, "Cannot delete yourself")
        
        cur = await db.execute("SELECT id FROM users WHERE id = ?", (user_id,))
        if not await cur.fetchone():
            raise HTTPException(404, "User not found")
        
        # Cascade will handle links, clicks, payments, subscriptions
        await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()
        
        logger.info(f"Admin deleted user {user_id}")
        return {"status": "deleted"}

    async def list_all_payments(self, db, page: int = 1, limit: int = 50, status: str = "") -> dict:
        """List all payments"""
        offset = (page - 1) * limit
        
        where_clause = "WHERE p.status = ?" if status else ""
        params = [status] if status else []
        
        cur = await db.execute(
            f"""SELECT COUNT(*) FROM payments p {where_clause}""",
            params
        )
        total = (await cur.fetchone())[0]
        
        cur = await db.execute(
            f"""SELECT p.id, p.payment_id, p.provider, p.plan, p.amount, p.currency, p.status, p.created_at,
                u.username, u.email
            FROM payments p JOIN users u ON p.user_id = u.id
            {where_clause}
            ORDER BY p.created_at DESC LIMIT ? OFFSET ?""",
            (*params, limit, offset)
        )
        rows = await cur.fetchall()
        
        payments = [
            {
                "id": r[0],
                "payment_id": r[1],
                "provider": r[2],
                "plan": r[3],
                "amount": r[4],
                "currency": r[5],
                "status": r[6],
                "created_at": datetime.fromtimestamp(r[7]),
                "username": r[8],
                "email": r[9]
            }
            for r in rows
        ]
        
        return {
            "items": payments,
            "total": total,
            "page": page,
            "limit": limit,
            "pages": (total + limit - 1) // limit
        }

    async def create_admin_user(self, db) -> None:
        """Create admin user if ADMIN_EMAIL is set and not exists"""
        if not config.ADMIN_EMAIL:
            return
        
        cur = await db.execute("SELECT id FROM users WHERE email = ?", (config.ADMIN_EMAIL,))
        if await cur.fetchone():
            # Ensure existing admin has admin role
            await db.execute("UPDATE users SET role = 'admin' WHERE email = ?", (config.ADMIN_EMAIL,))
            await db.commit()
            return
        
        if not config.ADMIN_PASSWORD:
            logger.warning("ADMIN_EMAIL set but ADMIN_PASSWORD not configured. Skipping admin creation.")
            return
        
        now = time.time()
        password_hash = hash_password(config.ADMIN_PASSWORD)
        
        await db.execute(
            """INSERT INTO users (username, email, password_hash, plan, role, email_verified, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            ("admin", config.ADMIN_EMAIL, password_hash, "business", "admin", 1, now, now)
        )
        await db.commit()
        logger.info(f"Admin user created: {config.ADMIN_EMAIL}")


admin_service = AdminService()
