import time
import json
import logging
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)

# Default ad settings
DEFAULTS = {
    "ad_enabled": "false",
    "ad_delay_seconds": "5",
    "ad_html": "",
    "ad_title": "Подождите...",
    "ad_skip_text": "Перейти к ссылке",
    "ad_plans_exempt": "pro,business",
}


class AdService:
    """Interstitial ad settings service (key-value store)"""

    async def get_all(self, db) -> dict:
        """Get all ad settings"""
        settings = dict(DEFAULTS)
        cur = await db.execute("SELECT key, value FROM settings WHERE key LIKE 'ad_%'")
        for row in await cur.fetchall():
            settings[row[0]] = row[1]
        return settings

    async def get(self, db, key: str, default: str = "") -> str:
        cur = await db.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = await cur.fetchone()
        return row[0] if row else default

    async def set(self, db, key: str, value: str):
        now = time.time()
        await db.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?",
            (key, value, now, value, now)
        )
        await db.commit()

    async def update(self, db, data: dict):
        """Update multiple ad settings"""
        for key, value in data.items():
            if key.startswith("ad_"):
                await self.set(db, key, str(value))

    async def should_show_ad(self, db, user_plan: str) -> bool:
        """Check if ad should be shown for this plan"""
        enabled = await self.get(db, "ad_enabled", "false")
        if enabled.lower() != "true":
            return False

        exempt_str = await self.get(db, "ad_plans_exempt", "pro,business")
        exempt_plans = [p.strip() for p in exempt_str.split(",") if p.strip()]
        return user_plan not in exempt_plans

    async def get_delay(self, db) -> int:
        """Get ad delay in seconds"""
        val = await self.get(db, "ad_delay_seconds", "5")
        try:
            return max(1, min(30, int(val)))
        except ValueError:
            return 5

    async def get_ad_html(self, db) -> str:
        """Get custom ad HTML code"""
        return await self.get(db, "ad_html", "")


ad_service = AdService()
