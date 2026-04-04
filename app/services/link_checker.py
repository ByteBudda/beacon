import logging
import re
import hashlib
import json
from urllib.parse import urlparse
from typing import Optional

import httpx

from app.core.config import config

logger = logging.getLogger(__name__)

# ========== BUILT-IN BLACKLIST ==========

BLACKLIST_DOMAINS = {
    # Фишинг / мошенничество
    "bit.ly", "tinyurl.com",  # вложенные сокращалки (будут проверены отдельно)
    "free-minecraft.ru", "free-vbucks.com", "free-robux.com",
    "login-microsoft.com", "login-google.com", "apple-id-verify.com",
    "wallet-connect.xyz", "metamask-io.com", "binance-secure.com",
    "crypto-giveaway.com", "elon-musk-gift.com", "btc-doubler.com",

    # Мальварь
    "crack-download.com", "keygen-download.com", "free-license-key.com",
    "activate-windows.com", "serial-key.com",

    # Фейковые магазины
    "aliexpress-sale.com", "amazon-prize.com", "ozon-sale.ru",
    "wildberries-sale.ru",
}

BLACKLIST_PATTERNS = [
    # Фишинг паттерны
    r"login.*(?:google|microsoft|apple|facebook|vk|yandex|mail\.ru|telegram)",
    r"(?:google|microsoft|apple|facebook|vk|yandex).*verify",
    r"(?:wallet|metamask|binance|crypto).*connect",
    r"(?:free|giveaway).*(?:robux|vbucks|minecraft|crypto|btc|eth)",
    r"(?:elon|tesla|spacex).*(?:giveaway|gift|btc|crypto)",
    r"(?:bank|sberbank|tinkoff|vtb|alfa).*login",
    r"(?:paypal|webmoney|qiwi).*verify",

    # Мальварь паттерны
    r"(?:crack|keygen|serial|activator|patch).*download",
    r"(?:free|download).*(?:license|activation|key).*\.(?:exe|msi|zip|rar)",

    # Вложенные сокращалки
    r"(?:bit\.ly|tinyurl\.com|t\.co|goo\.gl|is\.gd|v\.gd)/",
]

BLACKLIST_PATTERNS_COMPILED = [re.compile(p, re.IGNORECASE) for p in BLACKLIST_PATTERNS]


# ========== CHECKERS ==========

def check_blacklist(url: str) -> tuple[bool, str]:
    """Check URL against built-in blacklist. Returns (is_banned, reason)."""
    try:
        parsed = urlparse(url)
        domain = (parsed.hostname or "").lower()
    except Exception:
        return True, "Invalid URL"

    # Direct domain match
    if domain in BLACKLIST_DOMAINS:
        return True, f"Domain '{domain}' is blacklisted"

    # Subdomain check
    for blocked in BLACKLIST_DOMAINS:
        if domain.endswith("." + blocked):
            return True, f"Subdomain of '{blocked}' is blacklisted"

    # Pattern match on full URL
    url_lower = url.lower()
    for pattern in BLACKLIST_PATTERNS_COMPILED:
        if pattern.search(url_lower):
            return True, f"URL matches suspicious pattern"

    return False, ""


async def check_google_safe_browsing(url: str) -> tuple[bool, str]:
    """Check URL via Google Safe Browsing API v4. Returns (is_threat, threat_type)."""
    api_key = config.GOOGLE_SAFE_BROWSING_KEY
    if not api_key:
        return False, ""

    endpoint = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={api_key}"

    payload = {
        "client": {"clientId": "beacon", "clientVersion": "3.1.0"},
        "threatInfo": {
            "threatTypes": [
                "MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE",
                "POTENTIALLY_HARMFUL_APPLICATION", "THREAT_TYPE_UNSPECIFIED"
            ],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if data.get("matches"):
            threat = data["matches"][0]
            threat_type = threat.get("threatType", "UNKNOWN")
            logger.warning(f"Safe Browsing threat detected: {url} → {threat_type}")
            return True, threat_type
    except httpx.TimeoutException:
        logger.warning(f"Safe Browsing timeout for {url}")
    except Exception as e:
        logger.warning(f"Safe Browsing error: {e}")

    return False, ""


async def check_urlvirustotal(url: str) -> tuple[bool, str]:
    """Optional: Check via VirusTotal API."""
    api_key = config.VIRUSTOTAL_API_KEY
    if not api_key:
        return False, ""

    try:
        url_id = hashlib.sha256(url.encode()).hexdigest()
        endpoint = f"https://www.virustotal.com/api/v3/urls/{url_id}"

        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(endpoint, headers={"x-apikey": api_key})

        if resp.status_code == 200:
            data = resp.json()
            stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            malicious = stats.get("malicious", 0)
            if malicious >= 3:
                return True, f"VirusTotal: {malicious} engines flagged"
    except Exception as e:
        logger.warning(f"VirusTotal error: {e}")

    return False, ""


async def check_url(url: str) -> dict:
    """
    Full URL check: blacklist + Safe Browsing + VirusTotal.
    Returns: {"safe": bool, "status": str, "reason": str}
    status: "ok" | "blacklisted" | "phishing" | "malware" | "suspicious"
    """
    # 1. Built-in blacklist (fast, no API calls)
    banned, reason = check_blacklist(url)
    if banned:
        return {"safe": False, "status": "blacklisted", "reason": reason}

    # 2. Google Safe Browsing
    is_threat, threat_type = await check_google_safe_browsing(url)
    if is_threat:
        status_map = {
            "MALWARE": "malware",
            "SOCIAL_ENGINEERING": "phishing",
            "UNWANTED_SOFTWARE": "suspicious",
            "POTENTIALLY_HARMFUL_APPLICATION": "suspicious",
        }
        return {
            "safe": False,
            "status": status_map.get(threat_type, "suspicious"),
            "reason": f"Google Safe Browsing: {threat_type}",
        }

    # 3. VirusTotal (optional)
    is_vt_threat, vt_reason = await check_urlvirustotal(url)
    if is_vt_threat:
        return {"safe": False, "status": "malware", "reason": vt_reason}

    return {"safe": True, "status": "ok", "reason": ""}


link_checker = None  # module-level, used in services
