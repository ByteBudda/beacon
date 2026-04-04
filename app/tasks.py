import time
import logging
import asyncio
from datetime import datetime

from app.core.config import config

logger = logging.getLogger(__name__)


async def cleanup_expired_links(db):
    """Deactivate expired links"""
    now = time.time()
    try:
        cur = await db.execute(
            "SELECT COUNT(*) FROM links WHERE expires_at > 0 AND expires_at < ? AND is_active = 1",
            (now,)
        )
        count = (await cur.fetchone())[0]

        if count > 0:
            await db.execute(
                "UPDATE links SET is_active = 0 WHERE expires_at > 0 AND expires_at < ? AND is_active = 1",
                (now,)
            )
            await db.commit()
            logger.info(f"Deactivated {count} expired links")
    except Exception as e:
        logger.error(f"Cleanup expired links error: {e}")


async def cleanup_expired_subscriptions(db):
    """Downgrade users with expired subscriptions"""
    now = time.time()
    try:
        cur = await db.execute(
            "SELECT s.user_id FROM subscriptions s WHERE s.status = 'active' AND s.expires_at > 0 AND s.expires_at < ?",
            (now,)
        )
        rows = await cur.fetchall()

        for (user_id,) in rows:
            await db.execute("UPDATE subscriptions SET status = 'expired' WHERE user_id = ? AND status = 'active' AND expires_at < ?", (user_id, now))
            await db.execute("UPDATE users SET plan = 'free', updated_at = ? WHERE id = ?", (now, user_id))
            logger.info(f"User {user_id} subscription expired, downgraded to free")

        if rows:
            await db.commit()
            logger.info(f"Expired {len(rows)} subscriptions")
    except Exception as e:
        logger.error(f"Subscription cleanup error: {e}")


async def cleanup_old_clicks(db):
    """Remove click data older than 90 days"""
    cutoff = time.time() - (90 * 86400)
    try:
        cur = await db.execute("SELECT COUNT(*) FROM clicks WHERE ts < ?", (cutoff,))
        count = (await cur.fetchone())[0]
        if count > 0:
            await db.execute("DELETE FROM clicks WHERE ts < ?", (cutoff,))
            await db.commit()
            logger.info(f"Cleaned up {count} old click records")
    except Exception as e:
        logger.error(f"Click cleanup error: {e}")


async def cleanup_expired_trials(db):
    """End expired PRO trials"""
    try:
        from app.services.trial_service import trial_service
        count = await trial_service.end_expired_trials(db)
        if count > 0:
            logger.info(f"Ended {count} expired trials")
    except Exception as e:
        logger.error(f"Trial cleanup error: {e}")


async def background_worker(db, stop_event: asyncio.Event):
    """Background worker that runs periodic tasks"""
    logger.info("Background worker started")

    while not stop_event.is_set():
        try:
            await cleanup_expired_links(db)
            await cleanup_expired_subscriptions(db)
            await cleanup_expired_trials(db)
            await cleanup_old_clicks(db)
        except Exception as e:
            logger.error(f"Background worker error: {e}")

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=config.CLEANUP_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            pass

    logger.info("Background worker stopped")
