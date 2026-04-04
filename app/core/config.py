import os
from typing import List, Optional, Dict
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration - all settings from environment"""

    # Server
    SERVER_HOST: str = os.getenv("SERVER_HOST", "0.0.0.0")
    SERVER_PORT: int = int(os.getenv("SERVER_PORT", 3333))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info")
    LOG_FORMAT: str = os.getenv("LOG_FORMAT", "json")  # json or text

    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/beacon.db")
    DB_POOL_SIZE: int = int(os.getenv("DB_POOL_SIZE", "10"))
    DB_MAX_OVERFLOW: int = int(os.getenv("DB_MAX_OVERFLOW", "20"))

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    @property
    def redis_enabled(self) -> bool:
        return bool(self.REDIS_URL)

    # Alembic
    RUN_ALEMBIC_MIGRATIONS: bool = os.getenv("RUN_ALEMBIC_MIGRATIONS", "false").lower() == "true"

    # JWT
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRATION_HOURS: int = int(os.getenv("JWT_EXPIRATION_HOURS", 24))

    # Email
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "")
    FROM_NAME: str = os.getenv("FROM_NAME", "Beacon")
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

    @property
    def email_enabled(self) -> bool:
        return bool(self.SMTP_HOST and self.SMTP_USER and self.SMTP_PASSWORD)

    # App
    APP_NAME: str = os.getenv("APP_NAME", "Beacon")
    APP_URL: str = os.getenv("APP_URL", "http://localhost:3333")
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")
    CORS_ORIGINS: List[str] = os.getenv("CORS_ORIGINS", "*").split(",") if os.getenv("CORS_ORIGINS") else ["*"]

    # Rate Limiting
    RATE_LIMIT_REGISTER: int = int(os.getenv("RATE_LIMIT_REGISTER", 3))
    RATE_LIMIT_LOGIN: int = int(os.getenv("RATE_LIMIT_LOGIN", 5))
    RATE_LIMIT_CREATE_LINK: int = int(os.getenv("RATE_LIMIT_CREATE_LINK", 50))
    RATE_LIMIT_REDIRECT: int = int(os.getenv("RATE_LIMIT_REDIRECT", 200))
    RATE_LIMIT_WINDOW_HOURS: int = int(os.getenv("RATE_LIMIT_WINDOW_HOURS", 1))

    # Plan Limits
    PLAN_LIMITS: Dict[str, int] = {
        "free": int(os.getenv("FREE_PLAN_LIMIT", 50)),
        "pro": int(os.getenv("PRO_PLAN_LIMIT", 1000)),
        "business": int(os.getenv("BUSINESS_PLAN_LIMIT", 999999)),
    }

    PLAN_PRICES: Dict[str, int] = {
        "free": 0,
        "pro": int(os.getenv("PRO_PLAN_PRICE", 299)),
        "business": int(os.getenv("BUSINESS_PLAN_PRICE", 999)),
    }

    PLAN_FEATURES: Dict[str, Dict] = {
        "free": {
            "name": "Free", "links_limit": 50, "analytics_days": 7,
            "custom_slug": True, "qr_codes": True, "password_protection": False,
            "api_access": False, "priority_support": False, "custom_domains": False,
            "bulk_import": False, "og_tags": False, "trial_days": 0,
        },
        "pro": {
            "name": "Pro", "links_limit": 1000, "analytics_days": 30,
            "custom_slug": True, "qr_codes": True, "password_protection": True,
            "api_access": True, "priority_support": False, "custom_domains": False,
            "bulk_import": True, "og_tags": True, "trial_days": 7,
        },
        "business": {
            "name": "Business", "links_limit": 999999, "analytics_days": 365,
            "custom_slug": True, "qr_codes": True, "password_protection": True,
            "api_access": True, "priority_support": True, "custom_domains": True,
            "bulk_import": True, "og_tags": True, "trial_days": 0,
        },
    }

    # Payments
    YOOKASSA_SHOP_ID: str = os.getenv("YOOKASSA_SHOP_ID", "")
    YOOKASSA_SECRET_KEY: str = os.getenv("YOOKASSA_SECRET_KEY", "")

    @property
    def yookassa_enabled(self) -> bool:
        return bool(self.YOOKASSA_SHOP_ID and self.YOOKASSA_SECRET_KEY)

    YANDEX_PAY_MERCHANT_ID: str = os.getenv("YANDEX_PAY_MERCHANT_ID", "")
    YANDEX_PAY_SECRET_KEY: str = os.getenv("YANDEX_PAY_SECRET_KEY", "")

    @property
    def yandex_pay_enabled(self) -> bool:
        return bool(self.YANDEX_PAY_MERCHANT_ID and self.YANDEX_PAY_SECRET_KEY)

    # QR Code
    QR_CODE_SIZE: int = int(os.getenv("QR_CODE_SIZE", 10))
    QR_CODE_BORDER: int = int(os.getenv("QR_CODE_BORDER", 4))

    # Security
    BCRYPT_ROUNDS: int = int(os.getenv("BCRYPT_ROUNDS", 12))
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", "http://localhost:3333").split(",")
    TRUSTED_HOSTS: List[str] = os.getenv("TRUSTED_HOSTS", "localhost,qntx.ru").split(",")

    # Monitoring
    SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN")

    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_BOT_USERNAME: str = os.getenv("TELEGRAM_BOT_USERNAME", "")

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.TELEGRAM_BOT_TOKEN)

    # GeoIP
    GEOIP_DB_PATH: str = os.getenv("GEOIP_DB_PATH", "")

    # Link Moderation
    MODERATION_ENABLED: bool = os.getenv("MODERATION_ENABLED", "true").lower() == "true"
    GOOGLE_SAFE_BROWSING_KEY: str = os.getenv("GOOGLE_SAFE_BROWSING_KEY", "")
    VIRUSTOTAL_API_KEY: str = os.getenv("VIRUSTOTAL_API_KEY", "")
    AUTO_BAN_ON_DETECTION: bool = os.getenv("AUTO_BAN_ON_DETECTION", "true").lower() == "true"

    # Custom Domains
    DEFAULT_DOMAIN: str = os.getenv("DEFAULT_DOMAIN", "qntx.ru")

    # Background Tasks
    CLEANUP_INTERVAL_SECONDS: int = int(os.getenv("CLEANUP_INTERVAL_SECONDS", 3600))
    SUBSCRIPTION_CHECK_INTERVAL: int = int(os.getenv("SUBSCRIPTION_CHECK_INTERVAL", 3600))

    @classmethod
    def validate(cls):
        """Validate required configuration"""
        warnings = []
        if not cls.JWT_SECRET or len(cls.JWT_SECRET) < 32:
            warnings.append("JWT_SECRET is too weak! Generating new secret.")
            cls.JWT_SECRET = os.urandom(32).hex()
        
        if not cls.YOOKASSA_SECRET_KEY and cls.YOOKASSA_SHOP_ID:
            warnings.append("YOOKASSA_SECRET_KEY not set - webhook verification disabled")

        if not cls.email_enabled:
            warnings.append("Email not configured. Email features disabled.")

        if not cls.redis_enabled:
            warnings.append("Redis not configured. Using in-memory rate limiting.")

        if not cls.yookassa_enabled:
            warnings.append("YooKassa not configured. Payments in demo mode.")

        return warnings


config = Config()
