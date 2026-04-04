import time
import logging
import csv
import io
import json

from fastapi import APIRouter, Request, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse

from app.dependencies import get_current_user_id, get_db
from app.core.security import validate_url, generate_api_key, hash_api_key
from app.services.link_service import link_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/import-export", tags=["import-export"])


@router.post("/import/csv")
async def import_csv(file: UploadFile = File(...), request: Request = None, user_id: int = Depends(get_current_user_id)):
    """Import links from CSV file"""
    if not file.filename.endswith(".csv"):
        raise HTTPException(400, "File must be CSV")

    content = (await file.read()).decode("utf-8")
    reader = csv.DictReader(io.StringIO(content))

    db = request.app.state.db
    imported = 0
    errors = []

    for i, row in enumerate(reader, 1):
        url = row.get("url", "").strip()
        if not url:
            continue

        valid, err = validate_url(url)
        if not valid:
            errors.append(f"Row {i}: {err}")
            continue

        try:
            await link_service.create_link(
                {"url": url, "slug": row.get("slug", "").strip(), "title": row.get("title", "").strip()},
                user_id, db
            )
            imported += 1
        except Exception as e:
            errors.append(f"Row {i}: {e}")

    return {"imported": imported, "errors": errors[:20]}


@router.post("/import/json")
async def import_json(file: UploadFile = File(...), request: Request = None, user_id: int = Depends(get_current_user_id)):
    """Import links from JSON file"""
    content = (await file.read()).decode("utf-8")
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(400, "Invalid JSON")

    if not isinstance(data, list):
        raise HTTPException(400, "JSON must be an array of link objects")

    db = request.app.state.db
    imported = 0
    errors = []

    for i, item in enumerate(data, 1):
        url = item.get("url", "").strip()
        if not url:
            continue
        valid, err = validate_url(url)
        if not valid:
            errors.append(f"Item {i}: {err}")
            continue
        try:
            await link_service.create_link(
                {"url": url, "slug": item.get("slug", ""), "title": item.get("title", "")},
                user_id, db
            )
            imported += 1
        except Exception as e:
            errors.append(f"Item {i}: {e}")

    return {"imported": imported, "errors": errors[:20]}


@router.get("/export/csv")
async def export_csv(request: Request, user_id: int = Depends(get_current_user_id)):
    """Export all user links as CSV"""
    db = request.app.state.db
    cur = await db.execute(
        "SELECT slug, url, title, description, tags, clicks, created_at FROM links WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    rows = await cur.fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["slug", "url", "title", "description", "tags", "clicks", "created_at"])
    for r in rows:
        writer.writerow([r[0], r[1], r[2], r[3], r[4], r[5], time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r[6]))])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=beacon_links.csv"}
    )


@router.get("/export/json")
async def export_json(request: Request, user_id: int = Depends(get_current_user_id)):
    """Export all user links as JSON"""
    db = request.app.state.db
    cur = await db.execute(
        "SELECT slug, url, title, description, tags, clicks, created_at FROM links WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    rows = await cur.fetchall()

    links = [
        {
            "slug": r[0], "url": r[1], "title": r[2], "description": r[3],
            "tags": r[4], "clicks": r[5],
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(r[6]))
        }
        for r in rows
    ]

    return StreamingResponse(
        iter([json.dumps(links, ensure_ascii=False, indent=2)]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=beacon_links.json"}
    )
