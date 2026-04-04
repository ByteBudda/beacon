import logging
import time
import traceback

from fastapi import APIRouter, Request, Depends, HTTPException

from app.dependencies import get_current_user_id, require_verified
from app.models.schemas import LinkCreate, LinkUpdate, FolderCreate, FolderUpdate
from app.services.link_service import link_service
from app.core.config import config

logger = logging.getLogger("app.links")
logger.setLevel(logging.DEBUG)
router = APIRouter(prefix="/api/v1/links", tags=["links"])


# ========== FOLDERS ==========

@router.get("/folders")
async def list_folders(request: Request, user_id: int = Depends(get_current_user_id)):
    """List user folders with link counts"""
    db = request.app.state.db
    try:
        logger.debug(f"list_folders: user_id={user_id}")
        cur = await db.execute(
            """SELECT f.id, f.name, f.color, f.created_at, COUNT(l.id) as link_count 
               FROM folders f 
               LEFT JOIN links l ON l.folder_id = f.id AND l.is_active = 1 
               WHERE f.user_id = ? 
               GROUP BY f.id 
               ORDER BY f.name""",
            (user_id,)
        )
        rows = await cur.fetchall()
        logger.debug(f"list_folders: found {len(rows)} folders")
        return {
            "folders": [
                {"id": r[0], "name": r[1], "color": r[2], "created_at": r[3], "link_count": r[4] or 0}
                for r in rows
            ]
        }
    except Exception as e:
        logger.error(f"list_folders error: {e}\n{traceback.format_exc()}")
        raise


@router.post("/folders")
async def create_folder(f: FolderCreate, request: Request, user_id: int = Depends(get_current_user_id)):
    """Create folder"""
    db = request.app.state.db
    now = time.time()
    await db.execute(
        "INSERT INTO folders (user_id, name, color, created_at) VALUES (?,?,?,?)",
        (user_id, f.name, f.color or "#0078d4", now)
    )
    await db.commit()
    cur = await db.execute("SELECT last_insert_rowid()")
    row = await cur.fetchone()
    return {"id": row[0], "name": f.name, "color": f.color, "created_at": now}


@router.put("/folders/{folder_id}")
async def update_folder(folder_id: int, f: FolderUpdate, request: Request, user_id: int = Depends(get_current_user_id)):
    """Update folder"""
    db = request.app.state.db
    cur = await db.execute("SELECT id FROM folders WHERE id = ? AND user_id = ?", (folder_id, user_id))
    if not await cur.fetchone():
        raise HTTPException(404, "Folder not found")
    
    updates = {}
    if f.name is not None:
        updates["name"] = f.name
    if f.color is not None:
        updates["color"] = f.color
    
    if updates:
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        await db.execute(f"UPDATE folders SET {set_clause} WHERE id = ?", (*updates.values(), folder_id))
        await db.commit()
    
    return {"status": "ok"}


@router.delete("/folders/{folder_id}")
async def delete_folder(folder_id: int, request: Request, user_id: int = Depends(get_current_user_id)):
    """Delete folder"""
    db = request.app.state.db
    try:
        cur = await db.execute("SELECT id FROM folders WHERE id = ? AND user_id = ?", (folder_id, user_id))
        if not await cur.fetchone():
            raise HTTPException(404, "Folder not found")
        
        # Unlink links from folder
        await db.execute("UPDATE links SET folder_id = NULL WHERE folder_id = ?", (folder_id,))
        await db.execute("DELETE FROM folders WHERE id = ?", (folder_id,))
        await db.commit()
        
        logger.debug(f"delete_folder: folder_id={folder_id} deleted")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"delete_folder error: {e}\n{traceback.format_exc()}")
        raise


@router.post("")
async def create_link(l: LinkCreate, request: Request, user_id: int = Depends(get_current_user_id)):
    """Create short link (authenticated)"""
    db = request.app.state.db
    return await link_service.create_link(l.dict(), user_id, db)


@router.post("/anonymous")
async def create_link_anonymous(data: dict, request: Request):
    """Create anonymous short link (no auth, limited by device_id)"""
    import app.core.rate_limiter as rl_module
    
    db = request.app.state.db
    device_id = data.get("device_id", "")
    
    if not device_id:
        raise HTTPException(400, "device_id required")
    
    # Rate limit by device_id
    if rl_module.rate_limiter:
        if not await rl_module.rate_limiter.is_allowed(f"device_{device_id}", "anon_link"):
            raise HTTPException(403, "Anon limit reached. Create an account for unlimited links.")
    
    # Limited data for anonymous
    link_data = {
        "url": data.get("url", ""),
        "title": (data.get("title") or "")[:50],
    }
    # Anonymous links get random slug only
    link_data["slug"] = ""
    link_data["is_anonymous"] = True
    link_data["device_id"] = device_id
    
    # Check existing count for device
    cur = await db.execute(
        "SELECT COUNT(*) FROM links WHERE device_id = ? AND user_id = 0",
        (device_id,)
    )
    count = (await cur.fetchone())[0]
    
    if count >= 10:
        raise HTTPException(403, "Лимит исчерпан (10 ссылок). Создайте аккаунт для безлимитного использования.")
    
    return await link_service.create_link(link_data, 0, db)


@router.get("")
async def list_links(
    request: Request,
    user_id: int = Depends(get_current_user_id),
    q: str = "",
    page: int = 1,
    limit: int = 50,
    folder_id: int = None
):
    """List user links"""
    db = request.app.state.db
    return await link_service.list_links(user_id, db, q, page, limit, folder_id)


@router.get("/{link_id}")
async def get_link(link_id: int, request: Request, user_id: int = Depends(get_current_user_id)):
    """Get single link"""
    db = request.app.state.db
    return await link_service.get_link(link_id, user_id, db)


@router.get("/{link_id}/stats")
async def get_link_stats(
    link_id: int,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    days: int = 7
):
    """Get link statistics"""
    db = request.app.state.db
    return await link_service.get_link_stats(link_id, user_id, db, days)


@router.put("/{link_id}")
async def update_link(
    link_id: int,
    l: LinkUpdate,
    request: Request,
    user_id: int = Depends(get_current_user_id)
):
    """Update link"""
    db = request.app.state.db
    return await link_service.update_link(link_id, l.dict(), user_id, db)


@router.delete("/{link_id}")
async def delete_link(link_id: int, request: Request, user_id: int = Depends(get_current_user_id)):
    """Delete link"""
    db = request.app.state.db
    return await link_service.delete_link(link_id, user_id, db)


# ========== BULK CREATE ==========

@router.post("/bulk")
async def create_links_bulk(data: dict, request: Request, user_id: int = Depends(get_current_user_id)):
    """Create multiple links at once"""
    from app.core.security import validate_url
    
    db = request.app.state.db
    urls = data.get("urls", [])
    if not isinstance(urls, list) or len(urls) > 50:
        raise HTTPException(400, "Max 50 URLs at once")
    
    results = []
    for url in urls:
        try:
            # Validate URL - must be http/https
            if not url:
                raise ValueError("Empty URL")
            
            url_to_use = url.strip()
            
            # Check scheme BEFORE adding https://
            if url_to_use.startswith(("http://", "https://")):
                valid, error = validate_url(url_to_use)
                if not valid:
                    raise ValueError(error)
            elif "://" in url_to_use or url_to_use.startswith(("file://", "ftp://", "gopher://", "data:")):
                raise ValueError("Only http:// and https:// URLs allowed")
            else:
                # Add https:// prefix and validate
                url_to_use = f"https://{url_to_use}"
                valid, error = validate_url(url_to_use)
                if not valid:
                    raise ValueError(error)
            
            link_data = {"url": url_to_use}
            result = await link_service.create_link(link_data, user_id, db)
            slug = result.get("slug")
            short_url = f"{config.APP_URL}/s/{slug}"
            results.append({"url": url, "slug": slug, "short_url": short_url})
        except Exception as e:
            results.append({"url": url, "error": str(e)})
    
    return {"results": results, "total": len(results)}


# ========== QR CODE CUSTOM ==========

@router.get("/{link_id}/qr")
async def get_link_qr(
    link_id: int,
    request: Request,
    user_id: int = Depends(get_current_user_id),
    fill: str = None,
    back: str = None
):
    """Get custom QR code with colors"""
    db = request.app.state.db
    
    cur = await db.execute("SELECT slug, custom_domain, qr_fill_color, qr_back_color FROM links WHERE id = ? AND user_id = ?", (link_id, user_id))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Link not found")
    
    slug, custom_domain, db_fill, db_back = row
    
    # Use provided colors or fall back to stored defaults
    fill = fill or db_fill or "black"
    back = back or db_back or "white"
    
    from utils.qr_generator import qr_generator
    qr_code = qr_generator.generate_qr_code(slug, custom_domain, fill_color=fill, back_color=back)
    
    return {"qr_code": qr_code}


# ========== WEBHOOKS ==========

@router.post("/{link_id}/webhook")
async def add_webhook(link_id: int, data: dict, request: Request, user_id: int = Depends(get_current_user_id)):
    """Add webhook URL for link click notifications"""
    db = request.app.state.db
    
    cur = await db.execute("SELECT id FROM links WHERE id = ? AND user_id = ?", (link_id, user_id))
    if not await cur.fetchone():
        raise HTTPException(404, "Link not found")
    
    webhook_url = data.get("url", "").strip()
    if not webhook_url.startswith("http"):
        raise HTTPException(400, "Invalid webhook URL")
    
    import time
    now = time.time()
    await db.execute(
        "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
        (f"webhook_{link_id}", webhook_url, now)
    )
    await db.commit()
    
    return {"status": "ok", "webhook_url": webhook_url}


@router.delete("/{link_id}/webhook")
async def delete_webhook(link_id: int, request: Request, user_id: int = Depends(get_current_user_id)):
    """Remove webhook"""
    import json
    db = request.app.state.db
    
    cur = await db.execute("SELECT id FROM links WHERE id = ? AND user_id = ?", (link_id, user_id))
    if not await cur.fetchone():
        raise HTTPException(404, "Link not found")
    
    await db.execute("DELETE FROM settings WHERE key = ?", (f"webhook_{link_id}",))
    await db.commit()
    
    return {"status": "ok"}
