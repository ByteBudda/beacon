import time
import random
import string
import logging
import traceback
from datetime import datetime

from fastapi import HTTPException

from app.core.config import config
from app.core.security import hash_password
from app.services.link_checker import check_url
from utils.qr_generator import qr_generator
from utils.analytics import analytics

logger = logging.getLogger("app.link_service")
logger.setLevel(logging.DEBUG)


def clean_link(link: dict) -> dict:
    """Remove sensitive fields from link dict"""
    link.pop("password_hash", None)
    link["is_password_protected"] = bool(link.get("is_password_protected", 0))
    return link


def gen_slug(length=6):
    """Generate random slug"""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


class LinkService:
    """Link management service"""

    async def create_link(self, data: dict, user_id: int, db) -> dict:
        """Create short link"""
        # Check email verification
        cur = await db.execute("SELECT email_verified, plan FROM users WHERE id = ?", (user_id,))
        row = await cur.fetchone()
        if not row or not row[0]:
            raise HTTPException(403, "Please verify your email before creating links")
        
        plan = row[1]
        
        # Check plan limit
        cur = await db.execute("SELECT COUNT(*) FROM links WHERE user_id = ?", (user_id,))
        link_count = (await cur.fetchone())[0]
        
        if link_count >= config.PLAN_LIMITS.get(plan, 0):
            raise HTTPException(402, f"Link limit reached for your plan ({config.PLAN_LIMITS.get(plan, 0)} links)")
        
        slug = data.get("slug") or gen_slug()
        now = time.time()
        expires_hours = data.get("expires_hours", 0)
        expires = now + expires_hours * 3600 if expires_hours > 0 else 0
        
        # Check slug availability
        cur = await db.execute("SELECT id FROM links WHERE slug = ?", (slug,))
        if await cur.fetchone():
            raise HTTPException(409, "Slug already taken")
        
        # Hash password if needed
        password_hash = None
        if data.get("is_password_protected") and data.get("password"):
            password_hash = hash_password(data["password"])
        
        is_anon = data.get("is_anonymous", False)
        device_id = data.get("device_id", "") or ""
        
        import json
        geo_targets_str = ""
        if data.get("geo_targets"):
            geo_targets_str = json.dumps(data["geo_targets"])
        
        ab_urls_str = ""
        if data.get("ab_urls"):
            ab_urls_str = json.dumps(data["ab_urls"])
        
        await db.execute(
            """INSERT INTO links
            (user_id, slug, url, title, description, tags, created_at, expires_at,
             is_password_protected, password_hash, custom_domain, moderation_status,
             device_id, is_anonymous, geo_targets, ab_urls)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                user_id, slug, data["url"],
                data.get("title", ""), data.get("description", ""), data.get("tags", ""),
                now, expires, data.get("is_password_protected", False),
                password_hash, data.get("custom_domain"),
                ("pending" if config.MODERATION_ENABLED and not is_anon else "ok"),
                device_id, 1 if is_anon else 0, geo_targets_str, ab_urls_str
            )
        )
        await db.commit()

        # Auto-check URL for phishing/malware
        mod_status = "ok"
        mod_reason = ""
        if config.MODERATION_ENABLED:
            result = await check_url(data["url"])
            if not result["safe"]:
                mod_status = result["status"]
                mod_reason = result["reason"]
                if config.AUTO_BAN_ON_DETECTION:
                    await db.execute(
                        "UPDATE links SET moderation_status = ?, moderation_reason = ?, is_active = 0 WHERE slug = ?",
                        (mod_status, mod_reason, slug)
                    )
                else:
                    await db.execute(
                        "UPDATE links SET moderation_status = ?, moderation_reason = ? WHERE slug = ?",
                        (mod_status, mod_reason, slug)
                    )
                await db.commit()
                logger.warning(f"Link {slug} flagged: {mod_status} - {mod_reason}")
            else:
                await db.execute(
                    "UPDATE links SET moderation_status = 'ok' WHERE slug = ?", (slug,)
                )
                await db.commit()
        
        # Get created link
        cur = await db.execute("SELECT * FROM links WHERE slug = ?", (slug,))
        row = await cur.fetchone()
        cols = [d[0] for d in cur.description]
        link = dict(zip(cols, row))
        
        qr_code = qr_generator.generate_qr_code(slug, data.get("custom_domain"))
        
        logger.info(f"Link created: {slug} by user {user_id}")
        
        return clean_link({
            **link,
            "qr_code": qr_code,
            "created_at": datetime.fromtimestamp(link["created_at"]),
            "expires_at": datetime.fromtimestamp(link["expires_at"]) if link["expires_at"] else None
        })

    async def list_links(self, user_id: int, db, q: str = "", page: int = 1, limit: int = 50, folder_id: int = None) -> dict:
        """List user's links"""
        try:
            offset = (page - 1) * limit
            logger.debug(f"list_links: user_id={user_id}, q={q}, page={page}, limit={limit}, folder_id={folder_id}")
            
            base_where = "l.user_id = ?"
            params = [user_id]
            
            if folder_id:
                base_where += " AND l.folder_id = ?"
                params.append(folder_id)
        
            if q:
                search_where = base_where + " AND (l.title LIKE ? OR l.slug LIKE ? OR l.url LIKE ? OR l.tags LIKE ?)"
                search_params = params + [f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%"]
                cur = await db.execute(
                    f"""SELECT l.*, f.name as folder_name, s.value as webhook_url FROM links l 
                    LEFT JOIN folders f ON l.folder_id = f.id
                    LEFT JOIN settings s ON s.key = ('webhook_' || l.id)
                    WHERE {search_where}
                    ORDER BY l.created_at DESC LIMIT ? OFFSET ?""",
                    search_params + [limit, offset]
                )
                count_cur = await db.execute(
                    f"SELECT COUNT(*) FROM links l WHERE {search_where}",
                    search_params
                )
            else:
                cur = await db.execute(
                    f"""SELECT l.*, f.name as folder_name, s.value as webhook_url FROM links l 
                    LEFT JOIN folders f ON l.folder_id = f.id
                    LEFT JOIN settings s ON s.key = ('webhook_' || l.id)
                    WHERE {base_where}
                    ORDER BY l.created_at DESC LIMIT ? OFFSET ?""",
                    params + [limit, offset]
                )
                count_cur = await db.execute(
                    f"SELECT COUNT(*) FROM links l WHERE {base_where}",
                    params
                )
            
            rows = await cur.fetchall()
            cols = [d[0] for d in cur.description]
            
            total = (await count_cur.fetchone())[0]
            
            links = []
            for row in rows:
                link = dict(zip(cols, row))
                link["qr_code"] = qr_generator.generate_qr_code(link["slug"], link["custom_domain"])
                link["created_at"] = datetime.fromtimestamp(link["created_at"])
                link["expires_at"] = datetime.fromtimestamp(link["expires_at"]) if link["expires_at"] else None
                links.append(clean_link(link))
            
            return {"links": links, "page": page, "limit": limit, "total": total}
        except Exception as e:
            logger.error(f"list_links error: {e}\n{traceback.format_exc()}")
            raise

    async def get_link(self, link_id: int, user_id: int, db) -> dict:
        """Get single link"""
        cur = await db.execute(
            "SELECT * FROM links WHERE id = ? AND user_id = ?", (link_id, user_id)
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "Link not found")
        
        cols = [d[0] for d in cur.description]
        link = dict(zip(cols, row))
        
        # Get recent clicks
        cur = await db.execute(
            "SELECT * FROM clicks WHERE link_id = ? ORDER BY ts DESC LIMIT 100", (link_id,)
        )
        click_rows = await cur.fetchall()
        click_cols = [d[0] for d in cur.description]
        recent_clicks = [dict(zip(click_cols, c)) for c in click_rows]
        
        return clean_link({
            **link,
            "qr_code": qr_generator.generate_qr_code(link["slug"], link["custom_domain"]),
            "recent_clicks": recent_clicks,
            "created_at": datetime.fromtimestamp(link["created_at"]),
            "expires_at": datetime.fromtimestamp(link["expires_at"]) if link["expires_at"] else None
        })

    async def get_link_stats(self, link_id: int, user_id: int, db, days: int = 7) -> dict:
        """Get link analytics"""
        cur = await db.execute(
            "SELECT id, slug FROM links WHERE id = ? AND user_id = ?", (link_id, user_id)
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "Link not found")
        
        _, slug = row
        
        since = time.time() - (days * 86400)
        cur = await db.execute(
            "SELECT * FROM clicks WHERE link_id = ? AND ts > ? ORDER BY ts DESC",
            (link_id, since)
        )
        clicks_rows = await cur.fetchall()
        click_cols = [d[0] for d in cur.description]
        clicks_data = [dict(zip(click_cols, row)) for row in clicks_rows]
        
        stats = await analytics.get_aggregated_stats(clicks_data)
        
        return {
            "link_id": link_id,
            "slug": slug,
            **stats,
            "recent_clicks": clicks_data[:20]
        }

    async def update_link(self, link_id: int, data: dict, user_id: int, db) -> dict:
        """Update link"""
        cur = await db.execute(
            "SELECT id FROM links WHERE id = ? AND user_id = ?", (link_id, user_id)
        )
        if not await cur.fetchone():
            raise HTTPException(404, "Link not found")
        
        updates = {}
        for field in ("url", "title", "description", "tags", "qr_fill_color", "qr_back_color", "folder_id"):
            if data.get(field) is not None:
                updates[field] = data[field]
        
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            await db.execute(
                f"UPDATE links SET {set_clause} WHERE id = ?",
                (*updates.values(), link_id)
            )
            await db.commit()
        
        cur = await db.execute("SELECT * FROM links WHERE id = ?", (link_id,))
        row = await cur.fetchone()
        cols = [d[0] for d in cur.description]
        link = dict(zip(cols, row))
        
        logger.info(f"Link updated: {link['slug']}")
        
        return clean_link({
            **link,
            "qr_code": qr_generator.generate_qr_code(link["slug"], link["custom_domain"], 
                        fill_color=link.get("qr_fill_color", "#000000"), 
                        back_color=link.get("qr_back_color", "#ffffff")),
            "created_at": datetime.fromtimestamp(link["created_at"]),
            "expires_at": datetime.fromtimestamp(link["expires_at"]) if link["expires_at"] else None
        })

    async def delete_link(self, link_id: int, user_id: int, db) -> dict:
        """Delete link"""
        cur = await db.execute(
            "SELECT id, slug FROM links WHERE id = ? AND user_id = ?", (link_id, user_id)
        )
        row = await cur.fetchone()
        if not row:
            raise HTTPException(404, "Link not found")
        
        _, slug = row
        
        await db.execute("DELETE FROM clicks WHERE link_id = ?", (link_id,))
        await db.execute("DELETE FROM links WHERE id = ?", (link_id,))
        await db.commit()
        
        logger.info(f"Link deleted: {slug}")
        return {"status": "deleted"}


link_service = LinkService()
