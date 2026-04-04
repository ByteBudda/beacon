from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, field_validator, model_validator


# ========== USER MODELS ==========

class UserRegister(BaseModel):
    username: str
    email: EmailStr
    password: str
    referral_code: Optional[str] = None

    @field_validator("username")
    @classmethod
    def username_valid(cls, v: str) -> str:
        if len(v) < 3 or len(v) > 50:
            raise ValueError("Username must be between 3 and 50 characters")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, hyphens, underscores")
        return v

    @field_validator("password")
    @classmethod
    def password_strong(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain digit")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserProfile(BaseModel):
    id: int
    username: str
    email: EmailStr
    plan: str = "free"
    role: str = "user"
    links_count: int = 0
    total_clicks: int = 0
    created_at: datetime
    email_verified: bool = False
    is_active: bool = True


class PasswordReset(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


class ResendVerification(BaseModel):
    email: EmailStr


class ChangePassword(BaseModel):
    old_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strong(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not any(c.isupper() for c in v):
            raise ValueError("Password must contain uppercase letter")
        if not any(c.isdigit() for c in v):
            raise ValueError("Password must contain digit")
        return v


# ========== LINK MODELS ==========

class LinkCreate(BaseModel):
    url: str
    slug: str = ""
    title: str = ""
    description: str = ""
    tags: str = ""
    expires_hours: int = 0
    is_password_protected: bool = False
    password: Optional[str] = None
    custom_domain: Optional[str] = None
    folder_id: Optional[int] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    device_id: Optional[str] = None
    is_anonymous: bool = False
    geo_targets: Optional[dict] = None
    ab_urls: Optional[list] = None

    @field_validator("url")
    @classmethod
    def url_valid(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        if len(v) > 2000:
            raise ValueError("URL is too long")
        return v

    @field_validator("slug")
    @classmethod
    def slug_valid(cls, v: Optional[str]) -> Optional[str]:
        if v and (len(v) < 3 or len(v) > 50):
            raise ValueError("Slug must be 3-50 characters")
        if v and not v.replace("-", "").isalnum():
            raise ValueError("Slug can only contain alphanumeric and hyphens")
        return v or None


class LinkUpdate(BaseModel):
    url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[str] = None
    folder_id: Optional[int] = None
    expires_hours: Optional[int] = None
    geo_targets: Optional[dict] = None
    qr_fill_color: Optional[str] = None
    qr_back_color: Optional[str] = None


class FolderCreate(BaseModel):
    name: str
    color: Optional[str] = "#0078d4"


class FolderUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


class LinkResponse(BaseModel):
    id: int
    slug: str
    url: str
    title: str
    description: str
    tags: str
    clicks: int
    created_at: datetime
    expires_at: Optional[datetime]
    is_password_protected: bool
    qr_code: Optional[str] = None


class StatsResponse(BaseModel):
    link_id: int
    slug: str
    total_clicks: int
    clicks_by_device: dict
    clicks_by_browser: dict
    clicks_by_os: dict
    top_referrers: dict
    recent_clicks: List


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfile


# ========== PAYMENT MODELS ==========

class PaymentCreate(BaseModel):
    plan: str
    provider: str = "yookassa"

    @field_validator("plan")
    @classmethod
    def plan_valid(cls, v: str) -> str:
        if v not in ("pro", "business"):
            raise ValueError("Plan must be 'pro' or 'business'")
        return v

    @field_validator("provider")
    @classmethod
    def provider_valid(cls, v: str) -> str:
        if v not in ("yookassa", "yandex_pay"):
            raise ValueError("Provider must be 'yookassa' or 'yandex_pay'")
        return v


class PaymentResponse(BaseModel):
    id: int
    payment_id: str
    provider: str
    plan: str
    amount: float
    currency: str
    status: str
    confirmation_url: Optional[str] = None
    created_at: datetime


class PaymentStatus(BaseModel):
    payment_id: str
    status: str
    plan: str
    amount: float


class PlanInfo(BaseModel):
    name: str
    price: int
    links_limit: int
    analytics_days: int
    custom_slug: bool
    qr_codes: bool
    password_protection: bool
    api_access: bool
    priority_support: bool


# ========== ADMIN MODELS ==========

class AdminUserUpdate(BaseModel):
    plan: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None

    @field_validator("plan")
    @classmethod
    def plan_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("free", "pro", "business"):
            raise ValueError("Plan must be 'free', 'pro', or 'business'")
        return v

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("user", "admin"):
            raise ValueError("Role must be 'user' or 'admin'")
        return v


class AdminUserResponse(BaseModel):
    id: int
    username: str
    email: str
    plan: str
    role: str
    email_verified: bool
    is_active: bool
    links_count: int
    total_clicks: int
    created_at: datetime


class AdminStats(BaseModel):
    total_users: int
    active_users: int
    total_links: int
    total_clicks: int
    users_by_plan: dict
    recent_payments: List
    recent_users: List


class PaginatedResponse(BaseModel):
    items: List
    total: int
    page: int
    limit: int
    pages: int