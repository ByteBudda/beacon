import time
import logging

from app.core.config import config

logger = logging.getLogger("app.trial")


class TrialService:
    """PRO Trial management"""

    TRIAL_DAYS = 7

    async def start_trial(self, user_id: int, db) -> dict:
        """Start PRO trial for user"""
        now = time.time()
        
        # Check if user already had trial
        cur = await db.execute(
            "SELECT id FROM trial_periods WHERE user_id = ? AND is_active = 1",
            (user_id,)
        )
        if await cur.fetchone():
            return {"error": "Trial already active"}
        
        # Check trial eligibility
        cur = await db.execute(
            "SELECT trial_eligible FROM users WHERE id = ?",
            (user_id,)
        )
        row = await cur.fetchone()
        if not row or not row[0]:
            return {"error": "User not eligible for trial"}
        
        expires_at = now + (self.TRIAL_DAYS * 86400)
        
        await db.execute(
            """INSERT INTO trial_periods (user_id, plan, started_at, expires_at, is_active)
            VALUES (?, 'pro', ?, ?, 1)""",
            (user_id, now, expires_at)
        )
        
        # Upgrade user to PRO
        await db.execute(
            "UPDATE users SET plan = 'pro' WHERE id = ?",
            (user_id,)
        )
        
        await db.commit()
        
        logger.info(f"Trial started for user {user_id}, expires {expires_at}")
        
        return {
            "status": "trial_started",
            "plan": "pro",
            "expires_at": expires_at,
            "trial_days": self.TRIAL_DAYS
        }

    async def check_trial(self, user_id: int, db) -> dict:
        """Check if user has active trial"""
        now = time.time()
        
        cur = await db.execute(
            """SELECT id, plan, started_at, expires_at FROM trial_periods 
            WHERE user_id = ? AND is_active = 1 AND expires_at > ?""",
            (user_id, now)
        )
        row = await cur.fetchone()
        
        if not row:
            return {"has_trial": False}
        
        return {
            "has_trial": True,
            "plan": row[1],
            "started_at": row[2],
            "expires_at": row[3],
            "days_remaining": max(0, int((row[3] - now) / 86400))
        }

    async def end_expired_trials(self, db) -> int:
        """End expired trials and revert users to free"""
        now = time.time()
        
        cur = await db.execute(
            """SELECT user_id FROM trial_periods 
            WHERE is_active = 1 AND expires_at > 0 AND expires_at < ?""",
            (now,)
        )
        expired = await cur.fetchall()
        
        count = 0
        for row in expired:
            user_id = row[0]
            await db.execute(
                "UPDATE users SET plan = 'free' WHERE id = ? AND plan = 'pro'",
                (user_id,)
            )
            await db.execute(
                "UPDATE trial_periods SET is_active = 0 WHERE user_id = ?",
                (user_id,)
            )
            count += 1
        
        if count > 0:
            await db.commit()
            logger.info(f"Ended {count} expired trials")
        
        return count


trial_service = TrialService()