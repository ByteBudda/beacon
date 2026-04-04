import logging
from typing import Optional

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.core.security import decode_token, hash_api_key

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)


async def get_db(request: Request):
    """Get database connection"""
    return request.app.state.db


async def get_current_user_id(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> int:
    """Get authenticated user ID (JWT or API key)"""
    if not credentials:
        raise HTTPException(401, "Authentication required")

    token = credentials.credentials

    # Check if it's an API key
    if token.startswith("bcon_"):
        hashed = hash_api_key(token)
        db = request.app.state.db
        cur = await db.execute("SELECT id, is_active FROM users WHERE api_key = ?", (hashed,))
        row = await cur.fetchone()
        if not row:
            raise HTTPException(401, "Invalid API key")
        if not row[1]:
            raise HTTPException(403, "Account deactivated")
        return row[0]

    # JWT token
    try:
        payload = decode_token(token)
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(401, "Invalid token")
        return user_id
    except ValueError:
        raise HTTPException(401, "Invalid or expired token")


async def get_current_user(request: Request, user_id: int = Depends(get_current_user_id)) -> dict:
    """Get full current user data"""
    db = request.app.state.db
    cur = await db.execute(
        "SELECT id, username, email, plan, role, email_verified, is_active FROM users WHERE id = ?",
        (user_id,)
    )
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "User not found")

    user = {
        "id": row[0], "username": row[1], "email": row[2], "plan": row[3],
        "role": row[4], "email_verified": bool(row[5]), "is_active": bool(row[6])
    }
    if not user["is_active"]:
        raise HTTPException(403, "Account deactivated")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in ("admin", "superadmin"):
        raise HTTPException(403, "Admin access required")
    return user


async def require_superadmin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "superadmin":
        raise HTTPException(403, "Superadmin access required")
    return user


async def require_verified(user: dict = Depends(get_current_user)) -> dict:
    if not user["email_verified"]:
        raise HTTPException(403, "Email verification required")
    return user
