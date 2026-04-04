import time
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlparse

import bcrypt
from jose import jwt, JWTError

from app.core.config import config

logger = logging.getLogger(__name__)

# ========== PASSWORD ==========

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=config.BCRYPT_ROUNDS)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


# ========== JWT ==========

def create_access_token(user_id: int, extra: Optional[dict] = None) -> str:
    payload = {"user_id": user_id, "exp": datetime.utcnow() + timedelta(hours=config.JWT_EXPIRATION_HOURS)}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    except JWTError:
        raise ValueError("Invalid token")


def create_verification_token(email: str) -> str:
    return jwt.encode({"email": email, "exp": datetime.utcnow() + timedelta(hours=24)}, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def create_reset_token(user_id: int) -> str:
    return jwt.encode({"user_id": user_id, "exp": datetime.utcnow() + timedelta(hours=1)}, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


# ========== API KEYS ==========

def generate_api_key() -> str:
    return f"bcon_{secrets.token_hex(24)}"


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


# ========== SSRF PROTECTION ==========

BLOCKED_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.", "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.", "172.29.", "172.30.", "172.31.", "192.168."}
BLOCKED_SCHEMES = {"file", "ftp", "gopher", "data"}


def validate_url(url: str) -> tuple[bool, str]:
    """Validate URL for SSRF protection. Returns (is_valid, error_message)."""
    if len(url) > 2048:
        return False, "URL too long (max 2048 chars)"

    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Invalid URL format"

    if parsed.scheme not in ("http", "https"):
        return False, f"Scheme '{parsed.scheme}' not allowed"

    hostname = (parsed.hostname or "").lower()

    if not hostname:
        return False, "No hostname in URL"

    # Block internal addresses
    for blocked in BLOCKED_HOSTS:
        if hostname == blocked or hostname.startswith(blocked):
            return False, "Internal addresses not allowed"

    # Block custom ports that might be internal services
    if parsed.port and parsed.port in (22, 23, 25, 53, 110, 143, 389, 636, 3306, 5432, 6379, 8080, 9090):
        return False, f"Port {parsed.port} is blocked"

    return True, ""


# ========== PROMOCODE ==========

def validate_promocode(code: str) -> str:
    """Normalize promocode"""
    return code.strip().upper()
