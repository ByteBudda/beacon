import time
import logging
import json
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI

from app.core.config import config

logger = logging.getLogger(__name__)

# ========== SQL DDL ==========

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    plan TEXT DEFAULT 'free',
    role TEXT DEFAULT 'user',
    email_verified BOOLEAN DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    verification_token TEXT,
    api_key TEXT UNIQUE,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    url TEXT NOT NULL,
    title TEXT DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    created_at REAL NOT NULL,
    expires_at REAL DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    is_password_protected BOOLEAN DEFAULT 0,
    password_hash TEXT,
    custom_domain TEXT,
    og_title TEXT DEFAULT '',
    og_description TEXT DEFAULT '',
    og_image TEXT DEFAULT '',
    is_active BOOLEAN DEFAULT 1,
    moderation_status TEXT DEFAULT 'ok',
    moderation_reason TEXT DEFAULT '',
    device_id TEXT DEFAULT '',
    is_anonymous BOOLEAN DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id INTEGER NOT NULL,
    ip TEXT DEFAULT '',
    device_type TEXT DEFAULT '',
    os TEXT DEFAULT '',
    browser TEXT DEFAULT '',
    referer TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    country TEXT DEFAULT '',
    city TEXT DEFAULT '',
    ts REAL NOT NULL,
    FOREIGN KEY (link_id) REFERENCES links(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    payment_id TEXT UNIQUE NOT NULL,
    provider TEXT NOT NULL,
    plan TEXT NOT NULL,
    amount REAL NOT NULL,
    currency TEXT DEFAULT 'RUB',
    status TEXT DEFAULT 'pending',
    metadata TEXT DEFAULT '{}',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    payment_id TEXT,
    starts_at REAL NOT NULL,
    expires_at REAL,
    auto_renew BOOLEAN DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS promocodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT UNIQUE NOT NULL,
    plan TEXT NOT NULL,
    duration_days INTEGER DEFAULT 30,
    max_uses INTEGER DEFAULT 1,
    used_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT 1,
    expires_at REAL DEFAULT 0,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT DEFAULT '',
    target_id INTEGER DEFAULT 0,
    details TEXT DEFAULT '{}',
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key);
CREATE INDEX IF NOT EXISTS idx_links_user ON links(user_id);
CREATE INDEX IF NOT EXISTS idx_links_slug ON links(slug);
CREATE INDEX IF NOT EXISTS idx_links_expires ON links(expires_at);
CREATE INDEX IF NOT EXISTS idx_links_active ON links(is_active);
CREATE INDEX IF NOT EXISTS idx_clicks_link ON clicks(link_id);
CREATE INDEX IF NOT EXISTS idx_clicks_ts ON clicks(ts);
CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_expires ON subscriptions(expires_at);
CREATE INDEX IF NOT EXISTS idx_promocodes_code ON promocodes(code);

CREATE TABLE IF NOT EXISTS folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    color TEXT DEFAULT '#0078d4',
    created_at REAL NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_folders_user ON folders(user_id);

CREATE TABLE IF NOT EXISTS trial_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    plan TEXT NOT NULL,
    started_at REAL NOT NULL,
    expires_at REAL DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_trial_user ON trial_periods(user_id);
"""

# PostgreSQL uses slightly different types
PG_SCHEMA = SQL_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    plan VARCHAR(20) DEFAULT 'free',
    role VARCHAR(20) DEFAULT 'user',
    email_verified BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    verification_token TEXT,
    api_key VARCHAR(64) UNIQUE,
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS links (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slug VARCHAR(100) UNIQUE NOT NULL,
    url TEXT NOT NULL,
    title VARCHAR(500) DEFAULT '',
    description TEXT DEFAULT '',
    tags TEXT DEFAULT '',
    created_at DOUBLE PRECISION NOT NULL,
    expires_at DOUBLE PRECISION DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    is_password_protected BOOLEAN DEFAULT FALSE,
    password_hash TEXT,
    custom_domain VARCHAR(255),
    og_title VARCHAR(500) DEFAULT '',
    og_description TEXT DEFAULT '',
    og_image TEXT DEFAULT '',
    is_active BOOLEAN DEFAULT TRUE,
    moderation_status VARCHAR(20) DEFAULT 'ok',
    moderation_reason TEXT DEFAULT '',
    device_id VARCHAR(100) DEFAULT '',
    is_anonymous BOOLEAN DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS clicks (
    id SERIAL PRIMARY KEY,
    link_id INTEGER NOT NULL REFERENCES links(id) ON DELETE CASCADE,
    ip VARCHAR(45) DEFAULT '',
    device_type VARCHAR(20) DEFAULT '',
    os VARCHAR(50) DEFAULT '',
    browser VARCHAR(50) DEFAULT '',
    referer TEXT DEFAULT '',
    user_agent TEXT DEFAULT '',
    country VARCHAR(10) DEFAULT '',
    city VARCHAR(100) DEFAULT '',
    ts DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    payment_id VARCHAR(255) UNIQUE NOT NULL,
    provider VARCHAR(50) NOT NULL,
    plan VARCHAR(20) NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    currency VARCHAR(10) DEFAULT 'RUB',
    status VARCHAR(50) DEFAULT 'pending',
    metadata TEXT DEFAULT '{}',
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan VARCHAR(20) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    payment_id VARCHAR(255),
    starts_at DOUBLE PRECISION NOT NULL,
    expires_at DOUBLE PRECISION,
    auto_renew BOOLEAN DEFAULT FALSE,
    created_at DOUBLE PRECISION NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS promocodes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    plan VARCHAR(20) NOT NULL,
    duration_days INTEGER DEFAULT 30,
    max_uses INTEGER DEFAULT 1,
    used_count INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    expires_at DOUBLE PRECISION DEFAULT 0,
    created_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_logs (
    id SERIAL PRIMARY KEY,
    admin_id INTEGER NOT NULL,
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(50) DEFAULT '',
    target_id INTEGER DEFAULT 0,
    details TEXT DEFAULT '{}',
    created_at DOUBLE PRECISION NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key);
CREATE INDEX IF NOT EXISTS idx_links_user ON links(user_id);
CREATE INDEX IF NOT EXISTS idx_links_slug ON links(slug);
CREATE INDEX IF NOT EXISTS idx_links_expires ON links(expires_at);
CREATE INDEX IF NOT EXISTS idx_links_active ON links(is_active);
CREATE INDEX IF NOT EXISTS idx_clicks_link ON clicks(link_id);
CREATE INDEX IF NOT EXISTS idx_clicks_ts ON clicks(ts);
CREATE INDEX IF NOT EXISTS idx_payments_user ON payments(user_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_user ON subscriptions(user_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_expires ON subscriptions(expires_at);
CREATE INDEX IF NOT EXISTS idx_promocodes_code ON promocodes(code);

CREATE TABLE IF NOT EXISTS trial_periods (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan VARCHAR(20) NOT NULL,
    started_at DOUBLE PRECISION NOT NULL,
    expires_at DOUBLE PRECISION DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_trial_user ON trial_periods(user_id);
"""


def _is_postgres(url: str) -> bool:
    return "postgresql" in url or "asyncpg" in url


async def init_database(app: FastAPI):
    """Initialize database connection (SQLite or PostgreSQL)"""
    import aiosqlite

    if _is_postgres(config.DATABASE_URL):
        # PostgreSQL - for now use aiosqlite as fallback
        # In production, use asyncpg with SQLAlchemy async
        logger.info("PostgreSQL detected - using SQLite fallback for local dev")
        db_path = "data/beacon.db"
    else:
        db_path = config.DATABASE_URL.replace("sqlite:///", "").replace("sqlite://", "")

    import os
    os.makedirs(os.path.dirname(db_path) if "/" in db_path else ".", exist_ok=True)

    db = await aiosqlite.connect(db_path)
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")

    schema = PG_SCHEMA if _is_postgres(config.DATABASE_URL) else SQLITE_SCHEMA
    await db.executescript(schema)
    await db.commit()

    # Migrations for existing databases
    migrations = [
        "ALTER TABLE links ADD COLUMN moderation_status TEXT DEFAULT 'ok'",
        "ALTER TABLE links ADD COLUMN moderation_reason TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN api_key TEXT UNIQUE",
        "ALTER TABLE clicks ADD COLUMN country TEXT DEFAULT ''",
        "ALTER TABLE clicks ADD COLUMN city TEXT DEFAULT ''",
        "ALTER TABLE links ADD COLUMN device_id TEXT DEFAULT ''",
        "ALTER TABLE links ADD COLUMN is_anonymous INTEGER DEFAULT 0",
        "ALTER TABLE links ADD COLUMN geo_targets TEXT DEFAULT ''",
        "ALTER TABLE links ADD COLUMN ab_urls TEXT DEFAULT ''",
        "ALTER TABLE links ADD COLUMN qr_fill_color TEXT DEFAULT '#000000'",
        "ALTER TABLE links ADD COLUMN qr_back_color TEXT DEFAULT '#ffffff'",
        "ALTER TABLE users ADD COLUMN referral_code TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN referral_parent INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0",
        "ALTER TABLE links ADD COLUMN folder_id INTEGER",
        "ALTER TABLE links ADD FOREIGN KEY (folder_id) REFERENCES folders(id) ON DELETE SET NULL",
        "ALTER TABLE users ADD COLUMN trial_eligible INTEGER DEFAULT 1",
    ]
    for sql in migrations:
        try:
            await db.execute(sql)
        except Exception:
            pass  # column already exists
    await db.commit()

    # Create indexes after migrations
    for idx in [
        "CREATE INDEX IF NOT EXISTS idx_links_moderation ON links(moderation_status)",
    ]:
        try:
            await db.execute(idx)
        except Exception:
            pass
    await db.commit()

    # Run alembic migrations if configured
    if os.getenv("RUN_ALEMBIC_MIGRATIONS", "false").lower() == "true":
        try:
            import subprocess
            subprocess.run(["alembic", "upgrade", "head"], check=True)
            logger.info("Alembic migrations completed")
        except Exception as e:
            logger.warning(f"Alembic migration skipped: {e}")

    app.state.db = db
    logger.info(f"Database initialized: {config.DATABASE_URL[:50]}...")
    return db


async def close_database(app: FastAPI):
    """Close database connection"""
    if hasattr(app.state, "db") and app.state.db:
        await app.state.db.close()
        logger.info("Database closed")
