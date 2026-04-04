import time
import logging
from datetime import datetime, timedelta

from fastapi import HTTPException, BackgroundTasks

from app.core.config import config
from app.core.security import (
    hash_password, verify_password, create_access_token,
    create_verification_token, create_reset_token, decode_token
)
from utils.email_service import email_service
import app.core.rate_limiter as rl_module

logger = logging.getLogger(__name__)


class AuthService:
    """Authentication service"""

    async def register(self, username: str, email: str, password: str, referral_code: str = None, db = None, background_tasks = None) -> dict:
        """Register new user"""
        if rl_module.rate_limiter and not await rl_module.rate_limiter.is_allowed(f"register_{email}", "register"):
            raise HTTPException(status_code=429, detail="Too many registration attempts")
        
        # Check if email exists
        cur = await db.execute("SELECT id, email_verified FROM users WHERE email = ?", (email,))
        existing = await cur.fetchone()
        
        if existing:
            user_id, email_verified = existing
            if email_verified:
                raise HTTPException(status_code=409, detail="Email already registered")
            await db.execute("DELETE FROM users WHERE email = ?", (email,))
            await db.commit()
        
        # Check if username exists
        cur = await db.execute("SELECT id FROM users WHERE username = ?", (username,))
        if await cur.fetchone():
            raise HTTPException(status_code=409, detail="Username already taken")
        
        # Find referrer by referral code
        referral_parent = None
        if referral_code:
            cur = await db.execute("SELECT id FROM users WHERE referral_code = ?", (referral_code,))
            ref_row = await cur.fetchone()
            if ref_row:
                referral_parent = ref_row[0]
        
        # Create user
        password_hash = hash_password(password)
        verification_token = create_verification_token(email)
        now = time.time()
        
        await db.execute(
            """INSERT INTO users
            (username, email, password_hash, verification_token, created_at, updated_at, referral_parent)
            VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (username, email, password_hash, verification_token, now, now, referral_parent)
        )
        await db.commit()
        
        cur = await db.execute("SELECT id FROM users WHERE email = ?", (email,))
        user_id = (await cur.fetchone())[0]
        
        # Update referrer's count if there was a referral
        if referral_parent:
            await db.execute("UPDATE users SET referral_count = referral_count + 1 WHERE id = ?", (referral_parent,))
            await db.commit()
        
        # Ensure admin user gets admin role
        if email == config.ADMIN_EMAIL:
            await db.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))
            await db.commit()
        
        # Send verification email
        verification_link = f"{config.APP_URL}/verify?token={verification_token}"
        background_tasks.add_task(email_service.send_verification_email, email, verification_link)
        
        token = create_access_token(user_id)
        logger.info(f"User registered: {username} ({email})")
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": config.JWT_EXPIRATION_HOURS * 3600,
            "user": {
                "id": user_id,
                "username": username,
                "email": email,
                "plan": "free",
                "role": "user",
                "links_count": 0,
                "total_clicks": 0,
                "created_at": datetime.utcnow(),
                "email_verified": False
            }
        }

    async def login(self, email: str, password: str, db) -> dict:
        """Login user"""
        if rl_module.rate_limiter and not await rl_module.rate_limiter.is_allowed(f"login_{email}", "login"):
            raise HTTPException(status_code=429, detail="Too many login attempts")
        
        cur = await db.execute(
            "SELECT id, username, password_hash, plan, role, email_verified, is_active FROM users WHERE email = ?",
            (email,)
        )
        row = await cur.fetchone()
        
        if not row:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        user_id, username, password_hash, plan, role, email_verified, is_active = row
        
        if not verify_password(password, password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        
        if not email_verified:
            raise HTTPException(status_code=403, detail="Email not verified")
        
        if not is_active:
            raise HTTPException(status_code=403, detail="Account is deactivated")
        
        # Get stats
        cur = await db.execute("SELECT COUNT(*) FROM links WHERE user_id = ?", (user_id,))
        links_count = (await cur.fetchone())[0]
        
        cur = await db.execute("SELECT SUM(clicks) FROM links WHERE user_id = ?", (user_id,))
        total_clicks_row = await cur.fetchone()
        total_clicks = total_clicks_row[0] if total_clicks_row and total_clicks_row[0] else 0
        
        token = create_access_token(user_id, {"role": role})
        logger.info(f"User logged in: {username} ({email})")
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "expires_in": config.JWT_EXPIRATION_HOURS * 3600,
            "user": {
                "id": user_id,
                "username": username,
                "email": email,
                "plan": plan,
                "role": role,
                "links_count": links_count,
                "total_clicks": total_clicks,
                "created_at": datetime.utcnow(),
                "email_verified": True
            }
        }

    async def verify_email(self, token: str, db) -> dict:
        """Verify email by token"""
        try:
            payload = decode_token(token)
            email = payload.get("email")
            
            if not email:
                raise HTTPException(status_code=400, detail="Invalid verification token")
            
            cur = await db.execute("SELECT id, email_verified FROM users WHERE email = ?", (email,))
            row = await cur.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            
            user_id, email_verified = row
            
            if email_verified:
                return {"status": "Email already verified"}
            
            await db.execute(
                "UPDATE users SET email_verified = 1, verification_token = NULL WHERE email = ?",
                (email,)
            )
            await db.commit()
            
            # Send welcome email
            cur = await db.execute("SELECT username FROM users WHERE id = ?", (user_id,))
            username_row = await cur.fetchone()
            username = username_row[0] if username_row else "User"
            
            try:
                email_service.send_welcome_email(email, username)
            except Exception as e:
                logger.warning(f"Failed to send welcome email: {e}")
            
            logger.info(f"Email verified: {email}")
            return {"status": "Email verified successfully"}
            
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid or expired verification token")

    async def resend_verification(self, email: str, db, background_tasks: BackgroundTasks) -> dict:
        """Resend verification email"""
        if rl_module.rate_limiter and not await rl_module.rate_limiter.is_allowed(f"resend_{email}", "register"):
            raise HTTPException(status_code=429, detail="Too many requests")
        
        cur = await db.execute("SELECT id, email_verified, username FROM users WHERE email = ?", (email,))
        row = await cur.fetchone()
        
        if row and not row[1]:
            user_id, _, username = row
            verification_token = create_verification_token(email)
            
            await db.execute(
                "UPDATE users SET verification_token = ? WHERE id = ?",
                (verification_token, user_id)
            )
            await db.commit()
            
            verification_link = f"{config.APP_URL}/verify?token={verification_token}"
            background_tasks.add_task(email_service.send_verification_email, email, verification_link)
        
        return {"status": "success", "message": "If the email exists and is not verified, a new link has been sent"}

    async def request_password_reset(self, email: str, db, background_tasks: BackgroundTasks) -> dict:
        """Request password reset"""
        if rl_module.rate_limiter and not await rl_module.rate_limiter.is_allowed(f"password_reset_{email}", "register"):
            raise HTTPException(status_code=429, detail="Too many requests")
        
        cur = await db.execute("SELECT id, email_verified FROM users WHERE email = ?", (email,))
        row = await cur.fetchone()
        
        if row and row[1]:
            user_id = row[0]
            reset_token = create_reset_token(user_id)
            await db.execute(
                "UPDATE users SET verification_token = ? WHERE id = ?",
                (reset_token, user_id)
            )
            await db.commit()
            
            reset_link = f"{config.APP_URL}/reset?token={reset_token}"
            background_tasks.add_task(email_service.send_password_reset_email, email, reset_link)
        
        return {"status": "If email exists and is verified, password reset link has been sent"}

    async def confirm_password_reset(self, token: str, new_password: str, db) -> dict:
        """Confirm password reset"""
        try:
            payload = decode_token(token)
            user_id = payload.get("user_id")
            
            if not user_id:
                raise HTTPException(status_code=400, detail="Invalid reset token")
            
            password_hash = hash_password(new_password)
            await db.execute(
                "UPDATE users SET password_hash = ?, verification_token = NULL WHERE id = ?",
                (password_hash, user_id)
            )
            await db.commit()
            
            logger.info(f"Password reset for user {user_id}")
            return {"status": "success", "message": "Password reset successful"}
            
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    async def change_password(self, user_id: int, old_password: str, new_password: str, db) -> dict:
        """Change user password"""
        cur = await db.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
        row = await cur.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        
        if not verify_password(old_password, row[0]):
            raise HTTPException(status_code=401, detail="Current password is incorrect")
        
        new_password_hash = hash_password(new_password)
        await db.execute(
            "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
            (new_password_hash, time.time(), user_id)
        )
        await db.commit()
        
        return {"status": "success", "message": "Password changed successfully"}

    async def get_profile(self, user_id: int, db) -> dict:
        """Get user profile"""
        cur = await db.execute(
            "SELECT id, username, email, plan, role, email_verified, created_at FROM users WHERE id = ?",
            (user_id,)
        )
        row = await cur.fetchone()
        
        if not row:
            raise HTTPException(status_code=404, detail="User not found")
        
        cur = await db.execute("SELECT COUNT(*) FROM links WHERE user_id = ?", (user_id,))
        links_count = (await cur.fetchone())[0]
        
        cur = await db.execute("SELECT SUM(clicks) FROM links WHERE user_id = ?", (user_id,))
        total_clicks_row = await cur.fetchone()
        total_clicks = total_clicks_row[0] if total_clicks_row and total_clicks_row[0] else 0
        
        return {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "plan": row[3],
            "role": row[4],
            "email_verified": bool(row[5]),
            "links_count": links_count,
            "total_clicks": total_clicks,
            "created_at": datetime.fromtimestamp(row[6])
        }


auth_service = AuthService()
