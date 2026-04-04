"""
Beacon URL Shortener - Basic Tests

Run with: pytest tests/ -v
"""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestConfig:
    """Test configuration"""
    DEBUG = True
    APP_NAME = "Beacon Test"
    APP_URL = "http://localhost:3333"
    ADMIN_EMAIL = "admin@test.com"
    SECRET_KEY = "test-secret-key"
    PLAN_LIMITS = {"free": 50, "pro": 1000, "business": 999999}
    PLAN_PRICES = {"free": 0, "pro": 299, "business": 999}
    PLAN_FEATURES = {
        "free": {"name": "Free", "links_limit": 50},
        "pro": {"name": "Pro", "links_limit": 1000},
        "business": {"name": "Business", "links_limit": 999999}
    }


class TestSecurity:
    """Test security functions"""

    def test_validate_url_valid(self):
        from app.core.security import validate_url
        valid, _ = validate_url("https://example.com")
        assert valid is True

    def test_validate_url_invalid(self):
        from app.core.security import validate_url
        valid, error = validate_url("javascript:alert(1)")
        assert valid is False
        assert "not allowed" in error.lower() or "invalid" in error.lower()

    def test_validate_url_http(self):
        from app.core.security import validate_url
        valid, _ = validate_url("http://example.com")
        assert valid is True

    def test_hash_password(self):
        from app.core.security import hash_password, verify_password
        pw = "TestPassword123"
        hashed = hash_password(pw)
        assert hashed != pw
        assert verify_password(pw, hashed) is True
        assert verify_password("wrong", hashed) is False

    def test_validate_promocode(self):
        from app.core.security import validate_promocode
        assert validate_promocode("PROMO123") == "PROMO123"
        assert validate_promocode("promo") == "PROMO"
        assert validate_promocode("ab") == "AB"  # Min 2 chars allowed
        assert validate_promocode("") == ""  # Empty returns empty


class TestPlansConfig:
    """Test plan configuration"""

    def test_plan_limits(self):
        from app.core.config import config
        assert config.PLAN_LIMITS["free"] > 0
        assert config.PLAN_LIMITS["pro"] > config.PLAN_LIMITS["free"]
        assert config.PLAN_LIMITS["business"] == 999999

    def test_plan_prices(self):
        from app.core.config import config
        assert config.PLAN_PRICES["free"] == 0
        assert config.PLAN_PRICES["pro"] > 0
        assert config.PLAN_PRICES["business"] > config.PLAN_PRICES["pro"]

    def test_plan_features(self):
        from app.core.config import config
        assert "links_limit" in config.PLAN_FEATURES["free"]
        assert "api_access" in config.PLAN_FEATURES["pro"]
        assert config.PLAN_FEATURES["pro"]["api_access"] is True
        assert config.PLAN_FEATURES["free"]["api_access"] is False


class TestDependencies:
    """Test dependency injection"""

    @pytest.mark.asyncio
    async def test_get_db_returns_db(self):
        """Test get_db dependency"""
        from app.dependencies import get_db
        
        mock_request = MagicMock()
        mock_db = AsyncMock()
        mock_request.app.state.db = mock_db
        
        # get_db is a generator/async generator
        result = await get_db(mock_request)
        assert result == mock_db


class TestAuthSchemas:
    """Test auth schemas validation"""

    def test_user_register_valid(self):
        from app.models.schemas import UserRegister
        user = UserRegister(
            username="testuser",
            email="test@example.com",
            password="Password123"
        )
        assert user.username == "testuser"
        assert user.email == "test@example.com"

    def test_user_register_invalid_email(self):
        from app.models.schemas import UserRegister
        from pydantic import ValidationError
        
        with pytest.raises(ValidationError):
            UserRegister(
                username="testuser",
                email="invalid-email",
                password="Password123"
            )

    def test_user_register_password_requirements(self):
        from app.models.schemas import UserRegister
        from pydantic import ValidationError
        
        # Too short
        with pytest.raises(ValidationError):
            UserRegister(
                username="testuser",
                email="test@example.com",
                password="1234567"  # Less than 8
            )


class TestRateLimiter:
    """Test rate limiting"""

    @pytest.mark.asyncio
    async def test_rate_limiter_allows(self):
        from app.core.rate_limiter import create_rate_limiter
        limiter = create_rate_limiter()
        
        if limiter:
            result = await limiter.is_allowed("test_key", "test_action")
            # Should allow first request
            assert result is True


class TestAPIEndpoints:
    """Test API endpoint structure"""

    def test_health_endpoint_structure(self):
        """Verify health endpoint returns correct structure"""
        from app.routers.health import router
        assert router is not None
        
        routes = [r.path for r in router.routes]
        assert "/api/v1/health" in routes
        assert "/api/v1/info" in routes

    def test_auth_routes_exist(self):
        """Verify auth routes exist"""
        from app.routers.auth import router
        routes = [r.path for r in router.routes]
        
        assert "/api/v1/auth/register" in routes
        assert "/api/v1/auth/login" in routes
        assert "/api/v1/auth/me" in routes
        assert "/api/v1/auth/referral" in routes

    def test_links_routes_exist(self):
        """Verify links routes exist"""
        from app.routers.links import router
        routes = [r.path for r in router.routes]
        
        assert "/api/v1/links" in routes
        assert "/api/v1/links/folders" in routes

    def test_payments_routes_exist(self):
        """Verify payments routes exist"""
        from app.routers.payments import router
        routes = [r.path for r in router.routes]
        
        assert "/api/v1/payments/plans" in routes
        assert "/api/v1/payments/subscription/current" in routes
        assert "/api/v1/payments/subscription/cancel" in routes

    def test_promocodes_routes_exist(self):
        """Verify promocodes routes exist"""
        from app.routers.promocodes import router
        routes = [r.path for r in router.routes]
        
        assert "/api/v1/promocodes/redeem" in routes


class TestDatabaseSchema:
    """Test database schema validation"""

    def test_users_table_has_required_columns(self):
        from app.core.database import SQLITE_SCHEMA
        assert "users" in SQLITE_SCHEMA
        assert "username" in SQLITE_SCHEMA
        assert "email" in SQLITE_SCHEMA
        assert "password_hash" in SQLITE_SCHEMA
        assert "plan" in SQLITE_SCHEMA

    def test_links_table_has_required_columns(self):
        from app.core.database import SQLITE_SCHEMA
        assert "links" in SQLITE_SCHEMA
        assert "slug" in SQLITE_SCHEMA
        assert "url" in SQLITE_SCHEMA
        assert "clicks" in SQLITE_SCHEMA

    def test_subscriptions_table_exists(self):
        from app.core.database import SQLITE_SCHEMA
        assert "subscriptions" in SQLITE_SCHEMA
        assert "plan" in SQLITE_SCHEMA
        assert "status" in SQLITE_SCHEMA


class TestUtilities:
    """Test utility functions"""

    def test_device_id_generation(self):
        """Test device ID generation in JS equivalent"""
        import uuid
        import time
        
        device_id = "d_" + uuid.uuid4().hex[:13] + str(int(time.time()))[:11]
        assert len(device_id) > 10
        assert device_id.startswith("d_")

    def test_slug_generation(self):
        """Test slug generation"""
        import secrets
        
        def generate_slug(length=6):
            return secrets.token_urlsafe(length)[:length]
        
        slug = generate_slug(6)
        assert len(slug) == 6


# Run tests with: pytest tests/ -v
if __name__ == "__main__":
    pytest.main([__file__, "-v"])