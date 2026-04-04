import logging

from fastapi import APIRouter, Request, Depends, BackgroundTasks, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.dependencies import get_db, get_current_user_id, get_current_user
from app.models.schemas import UserRegister, UserLogin, PasswordReset, PasswordResetConfirm, ResendVerification, ChangePassword
from app.services.auth_service import auth_service
from app.core.config import config

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
security = HTTPBearer()


@router.post("/register")
async def register(user: UserRegister, request: Request, background_tasks: BackgroundTasks):
    """Register new user"""
    db = request.app.state.db
    return await auth_service.register(user.username, user.email, user.password, user.referral_code, db, background_tasks)


@router.post("/login")
async def login(user: UserLogin, request: Request):
    """Login user"""
    db = request.app.state.db
    return await auth_service.login(user.email, user.password, db)


@router.get("/verify-email")
async def verify_email(token: str, request: Request):
    """Verify email"""
    db = request.app.state.db
    return await auth_service.verify_email(token, db)


@router.post("/resend-verification")
async def resend_verification(data: ResendVerification, request: Request, background_tasks: BackgroundTasks):
    """Resend verification email"""
    db = request.app.state.db
    return await auth_service.resend_verification(data.email, db, background_tasks)


@router.get("/check-verification")
async def check_verification(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Check if email is verified"""
    from app.core.security import decode_token
    try:
        payload = decode_token(credentials.credentials)
        user_id = payload.get("user_id")
        db = request.app.state.db
        cur = await db.execute("SELECT email_verified FROM users WHERE id = ?", (user_id,))
        row = await cur.fetchone()
        return {"email_verified": bool(row[0]) if row else False}
    except ValueError:
        raise HTTPException(401, "Invalid token")


@router.post("/password-reset")
async def request_password_reset(data: PasswordReset, request: Request, background_tasks: BackgroundTasks):
    """Request password reset"""
    db = request.app.state.db
    return await auth_service.request_password_reset(data.email, db, background_tasks)


@router.post("/password-reset-confirm")
async def confirm_password_reset(data: PasswordResetConfirm, request: Request):
    """Confirm password reset"""
    db = request.app.state.db
    return await auth_service.confirm_password_reset(data.token, data.new_password, db)


@router.post("/change-password")
async def change_password(data: ChangePassword, request: Request, user_id: int = Depends(get_current_user_id)):
    """Change password"""
    db = request.app.state.db
    return await auth_service.change_password(user_id, data.old_password, data.new_password, db)


@router.get("/profile")
async def get_profile(request: Request, user_id: int = Depends(get_current_user_id)):
    """Get user profile"""
    db = request.app.state.db
    return await auth_service.get_profile(user_id, db)


@router.get("/me")
async def get_current(request: Request, user_id: int = Depends(get_current_user_id), db = Depends(get_db)):
    """Get current user info for auth check"""
    cur = await db.execute(
        "SELECT id, username, email, plan, role, email_verified, is_active FROM users WHERE id = ?",
        (user_id,)
    )
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "User not found")
    return {
        "id": row[0],
        "username": row[1],
        "email": row[2],
        "plan": row[3],
        "role": row[4],
        "email_verified": bool(row[5]),
        "is_active": bool(row[6])
    }


# ========== REFERRAL ==========

@router.get("/referral")
async def get_referral_info(request: Request, user_id: int = Depends(get_current_user_id)):
    """Get user's referral info"""
    db = request.app.state.db
    
    cur = await db.execute("SELECT username, referral_code, referral_count FROM users WHERE id = ?", (user_id,))
    row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "User not found")
    
    username, referral_code, referral_count = row
    
    # Generate referral code if not exists
    if not referral_code:
        import secrets
        referral_code = secrets.token_urlsafe(6)[:8]
        await db.execute("UPDATE users SET referral_code = ? WHERE id = ?", (referral_code, user_id))
        await db.commit()
    
    referral_link = f"{config.APP_URL}/register?ref={referral_code}"
    bonus_earned = referral_count * 10  # 10 bonus per referral
    
    # Get actual referrals
    cur = await db.execute(
        "SELECT id, username, email, plan, created_at FROM users WHERE referral_parent = ? ORDER BY created_at DESC",
        (user_id,)
    )
    ref_rows = await cur.fetchall()
    referrals = [
        {"id": r[0], "username": r[1], "email": r[2], "plan": r[3], "created_at": r[4]}
        for r in ref_rows
    ]
    
    return {
        "referral_code": referral_code,
        "referral_link": referral_link,
        "referral_count": len(referrals),
        "bonus_earned": bonus_earned,
        "pending_referrals": 0,
        "referrals": referrals
    }
