# Beacon URL Shortener - API Documentation

## Version: v1 (Stable)

All API endpoints use the `/api/v1/` prefix.

---

## Table of Contents
1. [Project Structure](#project-structure)
2. [Database Schema](#database-schema)
3. [Plans & Features](#plans--features)
4. [API Routes](#api-routes)
5. [CLI Commands](#cli-commands)
6. [Error Responses](#error-responses)

---

## Project Structure

```
beaconqntx-full/
├── app/
│   ├── bot/                    # Telegram bot
│   │   └── telegram_bot.py
│   ├── core/                   # Core utilities
│   │   ├── config.py           # Configuration (env vars)
│   │   ├── database.py         # DB initialization & schema
│   │   ├── security.py         # JWT, passwords, URL validation
│   │   ├── rate_limiter.py     # Rate limiting
│   │   └── logging.py
│   ├── models/
│   │   └── schemas.py          # Pydantic models
│   ├── routers/                # API endpoints (all use /api/v1/*)
│   │   ├── auth.py             # /api/v1/auth/*
│   │   ├── links.py            # /api/v1/links/*
│   │   ├── account.py          # /api/v1/account/*
│   │   ├── payments.py         # /api/v1/payments/*
│   │   ├── promocodes.py       # /api/v1/promocodes/*
│   │   ├── admin.py            # /api/v1/admin/*
│   │   ├── import_export.py    # /api/v1/import-export/*
│   │   ├── settings.py         # /api/v1/settings/*
│   │   ├── ad.py               # /api/v1/ads/*
│   │   └── health.py           # /api/v1/health, /api/v1/info
│   ├── services/                # Business logic
│   ├── middleware/             # Custom middleware
│   │   ├── __init__.py         # Error handling, security headers
│   │   └── logging.py          # Request logging with request ID
│   ├── cli.py                  # Management CLI
│   └── main.py                 # FastAPI app
├── static/                     # Frontend
├── tests/                      # Tests
└── data/
    └── beacon.db               # SQLite database
```

---

## Base URL
```
/api/v1
```

## Authentication
- **JWT Token**: Header `Authorization: Bearer <token>`
- **API Key**: Header `Authorization: Bearer bcon_<key>`

---

## CLI Commands

```bash
# User management
python -m app.cli user list --limit 20
python -m app.cli user create --username admin --email admin@example.com --password xxx --plan pro --role admin
python -m app.cli user reset-password --email user@example.com --password newpass
python -m app.cli user delete --email user@example.com

# Database
python -m app.cli db status
python -m app.cli db cleanup

# Promocodes
python -m app.cli promo create --code PROMO20 --plan pro --days 30 --max-uses 100
python -m app.cli promo list

# Stats
python -m app.cli stats
python -m app.cli health
```

---

## API Routes
│   │   ├── account.py           # /api/v1/account/*
│   │   ├── payments.py          # /api/payments/*
│   │   ├── promocodes.py        # /api/v1/promocodes/*
│   │   ├── admin.py             # /api/admin/*
│   │   ├── import_export.py     # /api/v1/import-export/*
│   │   ├── settings.py          # Site settings
│   │   ├── ad.py                # Ad management
│   │   └── health.py            # Health checks
│   ├── services/                # Business logic
│   │   ├── auth_service.py
│   │   ├── link_service.py
│   │   ├── payment_service.py
│   │   ├── admin_service.py
│   │   ├── trial_service.py
│   │   └── ad_service.py
│   ├── dependencies.py          # Auth dependencies
│   └── main.py                  # FastAPI app
├── static/                      # Frontend
│   ├── index.html
│   ├── app.js
│   └── style.css
└── data/
    └── beacon.db                # SQLite database
```

---

## Database Schema

### users
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | User ID |
| username | TEXT UNIQUE | Username |
| email | TEXT UNIQUE | Email |
| password_hash | TEXT | Bcrypt hash |
| plan | TEXT | free/pro/business |
| role | TEXT | user/admin/superadmin |
| email_verified | BOOLEAN | Email verified |
| is_active | BOOLEAN | Account active |
| api_key | TEXT UNIQUE | API key (hashed) |
| referral_code | TEXT | Referral code |
| referral_parent | INTEGER | Referrer user ID |
| referral_count | INTEGER | Number of referrals |
| created_at | REAL | Unix timestamp |
| updated_at | REAL | Unix timestamp |

### links
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Link ID |
| user_id | INTEGER FK | Owner user_id |
| slug | TEXT UNIQUE | Short URL alias |
| url | TEXT | Original URL |
| title | TEXT | Link title |
| description | TEXT | Description |
| tags | TEXT | Tags (JSON) |
| clicks | INTEGER | Click count |
| is_password_protected | BOOLEAN | Has password |
| password_hash | TEXT | Password hash |
| folder_id | INTEGER FK | Folder ID |
| qr_fill_color | TEXT | QR fill color |
| qr_back_color | TEXT | QR background color |
| geo_targets | TEXT | Geo-targeting (JSON) |
| ab_urls | TEXT | A/B test URLs (JSON) |
| is_anonymous | BOOLEAN | Anonymous link |
| device_id | TEXT | Device ID for anon |
| is_active | BOOLEAN | Link active |
| moderation_status | TEXT | ok/pending/blacklisted/phishing/malware |
| created_at | REAL | Unix timestamp |
| expires_at | REAL | Expiration timestamp |

### clicks
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Click ID |
| link_id | INTEGER FK | Link ID |
| ip | TEXT | IP address |
| device_type | TEXT | desktop/mobile/bot |
| os | TEXT | Operating system |
| browser | TEXT | Browser |
| referer | TEXT | Referrer URL |
| user_agent | TEXT | User agent string |
| country | TEXT | Country code |
| city | TEXT | City name |
| ts | REAL | Timestamp |

### subscriptions
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Subscription ID |
| user_id | INTEGER FK | User ID |
| plan | TEXT | free/pro/business |
| status | TEXT | active/expired/canceled |
| payment_id | TEXT | Payment ID |
| starts_at | REAL | Start timestamp |
| expires_at | REAL | Expiration timestamp |
| auto_renew | BOOLEAN | Auto-renew enabled |
| created_at | REAL | Created timestamp |
| updated_at | REAL | Updated timestamp |

### payments
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Payment ID |
| user_id | INTEGER FK | User ID |
| payment_id | TEXT UNIQUE | External payment ID |
| provider | TEXT | yookassa/yandex_pay |
| plan | TEXT | Plan name |
| amount | REAL | Amount |
| currency | TEXT | Currency (RUB) |
| status | TEXT | pending/completed/canceled |
| metadata | TEXT | JSON metadata |
| created_at | REAL | Created timestamp |
| updated_at | REAL | Updated timestamp |

### folders
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Folder ID |
| user_id | INTEGER FK | Owner user_id |
| name | TEXT | Folder name |
| color | TEXT | Color hex code |
| created_at | REAL | Created timestamp |

### promocodes
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PK | Promocode ID |
| code | TEXT UNIQUE | Promo code |
| plan | TEXT | pro/business |
| duration_days | INTEGER | Days to add |
| max_uses | INTEGER | Max uses |
| used_count | INTEGER | Times used |
| is_active | BOOLEAN | Is active |
| expires_at | REAL | Expiration timestamp |
| created_at | REAL | Created timestamp |

### settings (key-value store)
| Column | Type | Description |
|--------|------|-------------|
| key | TEXT PK | Setting key |
| value | TEXT | Setting value |
| updated_at | REAL | Updated timestamp |

---

## Plans & Features

| Feature | Free | Pro | Business |
|---------|------|-----|----------|
| links_limit | 50 | 1000 | Unlimited |
| analytics_days | 7 | 30 | 365 |
| custom_slug | ✅ | ✅ | ✅ |
| qr_codes | ✅ | ✅ | ✅ |
| password_protection | ❌ | ✅ | ✅ |
| api_access | ❌ | ✅ | ✅ |
| priority_support | ❌ | ❌ | ✅ |
| custom_domains | ❌ | ❌ | ✅ |
| bulk_import | ❌ | ✅ | ✅ |
| og_tags | ❌ | ✅ | ✅ |
| trial_days | 0 | 7 | 0 |
| **Price** | 0 | 299₽/mo | 999₽/mo |

**Config location:** `app/core/config.py` (PLAN_LIMITS, PLAN_PRICES, PLAN_FEATURES)

---

## API Routes

### Auth Routes (`/api/auth`)

### POST /auth/register
Register new user.
```json
{
  "username": "string",
  "email": "user@example.com",
  "password": "Password123",
  "referral_code": "optional"
}
```
**Response:**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": { "id": 1, "username": "...", "email": "...", "plan": "free" }
}
```

### POST /auth/login
Login user.
```json
{
  "email": "user@example.com",
  "password": "Password123"
}
```
**Response:** Same as register.

### GET /auth/verify-email?token=<token>
Verify email address. Returns redirect or JSON status.

### POST /auth/resend-verification
Resend verification email.
```json
{ "email": "user@example.com" }
```

### GET /auth/check-verification
Check if email is verified. Requires Bearer token.
**Response:** `{ "email_verified": true/false }`

### POST /auth/password-reset
Request password reset.
```json
{ "email": "user@example.com" }
```

### POST /auth/password-reset-confirm
Confirm password reset.
```json
{
  "token": "reset_token",
  "new_password": "NewPassword123"
}
```

### POST /auth/change-password
Change password (authenticated).
```json
{
  "old_password": "OldPassword123",
  "new_password": "NewPassword123"
}
```
Requires: Bearer token

### GET /auth/profile
Get user profile. Requires: Bearer token
**Response:** User profile object

### GET /auth/me
Get current user info. Requires: Bearer token
```json
{
  "id": 1,
  "username": "string",
  "email": "string",
  "plan": "free|pro|business",
  "role": "user|admin|superadmin",
  "email_verified": true/false,
  "is_active": true/false
}
```

### GET /auth/referral
Get user's referral info. Requires: Bearer token
```json
{
  "referral_code": "abc123xy",
  "referral_link": "https://beacon.app/register?ref=abc123xy",
  "referral_count": 5,
  "bonus_earned": 50,
  "pending_referrals": 0,
  "referrals": [
    { "id": 1, "username": "...", "email": "...", "plan": "pro", "created_at": 1234567890 }
  ]
}
```

---

## Links Routes (`/api/links`)

### POST /links
Create short link (authenticated).
```json
{
  "url": "https://example.com",
  "slug": "custom-alias",        // optional
  "title": "My Link",           // optional
  "is_password_protected": true, // optional
  "password": "secret123",      // optional
  "folder_id": 1,               // optional
  "utm_source": "google",       // optional
  "utm_medium": "cpc",          // optional
  "utm_campaign": "summer",     // optional
  "geo_targets": { "RU": "https://ru.example.com" }, // optional
  "ab_urls": ["https://a.com", "https://b.com"]     // optional
}
```
Requires: Bearer token

**Response:**
```json
{
  "id": 1,
  "slug": "abc123",
  "url": "https://example.com",
  "short_url": "https://beacon.app/s/abc123",
  "qr_code": "data:image/png;base64,..."
}
```

### POST /links/anonymous
Create anonymous link (no auth, limited).
```json
{
  "url": "https://example.com",
  "device_id": "device_identifier"
}
```
**Limit:** 10 links per device

### GET /links
List user links. Requires: Bearer token
- Query params: `?q=search&page=1&limit=50&folder_id=1`

**Response:**
```json
{
  "items": [...],
  "total": 100,
  "page": 1,
  "limit": 50
}
```

### GET /links/{link_id}
Get single link details. Requires: Bearer token

### GET /links/{link_id}/stats
Get link statistics. Requires: Bearer token
- Query param: `?days=7`

**Response:**
```json
{
  "total_clicks": 1000,
  "clicks_by_device": { "desktop": 600, "mobile": 400 },
  "clicks_by_os": { "Windows": 500, "Android": 300, "iOS": 200 },
  "clicks_by_browser": { "Chrome": 700, "Safari": 200, "Firefox": 100 },
  "top_referrers": { "google.com": 300, "direct": 500 },
  "recent_clicks": [...]
}
```

### PUT /links/{link_id}
Update link. Requires: Bearer token
```json
{
  "url": "https://new-url.com",
  "title": "New Title",
  "is_password_protected": true,
  "password": "newpass",
  "qr_fill_color": "#000000",
  "qr_back_color": "#ffffff"
}
```

### DELETE /links/{link_id}
Delete link. Requires: Bearer token

### GET /links/{link_id}/qr
Get custom QR code with colors.
- Query params: `?fill=black&back=white`

### POST /links/{link_id}/webhook
Add webhook URL for click notifications.
```json
{ "url": "https://your-site.com/webhook" }
```

### DELETE /links/{link_id}/webhook
Remove webhook.

### POST /links/bulk
Create multiple links at once.
```json
{
  "urls": ["https://example1.com", "https://example2.com"]
}
```
Max 50 URLs.

---

## Folders Routes (`/api/links/folders`)

### GET /links/folders
List user folders with link counts.
```json
{
  "folders": [
    { "id": 1, "name": "Work", "color": "#0078d4", "created_at": 1234567890, "link_count": 10 }
  ]
}
```

### POST /links/folders
Create folder.
```json
{ "name": "My Folder", "color": "#ff0000" }
```

### PUT /links/folders/{folder_id}
Update folder.
```json
{ "name": "New Name", "color": "#00ff00" }
```

### DELETE /links/folders/{folder_id}
Delete folder (links remain).

---

## Account Routes (`/api/v1/account`)

### GET /account
Get account details. Requires: Bearer token
```json
{
  "id": 1,
  "username": "string",
  "email": "string",
  "plan": "free|pro|business",
  "role": "user|admin",
  "email_verified": true,
  "has_api_key": true,
  "created_at": 1234567890,
  "links_count": 50,
  "total_clicks": 1000,
  "referral_count": 5,
  "plan_limit": 50,
  "subscription": { "plan": "pro", "status": "active", "expires_at": 1234567890 }
}
```

### PUT /account/email
Change email.
```json
{
  "new_email": "new@example.com",
  "password": "Password123"
}
```
Requires: Bearer token

### GET /account/api-key
Check if API key exists.
```json
{ "has_api_key": true }
```

### POST /account/api-key
Generate new API key. Requires Pro/Business plan.
```json
{ "api_key": "bcon_abc123...", "message": "Save this key..." }
```

### DELETE /account/api-key
Revoke API key.

### DELETE /account
Delete account.
```json
{ "password": "Password123" }
```

---

## Payments Routes (`/api/payments`)

### GET /payments/plans
Get available plans.
```json
{
  "plans": [
    {
      "id": "free",
      "name": "Free",
      "price": 0,
      "custom_slug": false,
      "qr_codes": false,
      "password_protection": false,
      "api_access": false,
      "priority_support": false,
      "links_limit": 50,
      "analytics_days": 7
    },
    {
      "id": "pro",
      "name": "Pro",
      "price": 299,
      ...
    },
    {
      "id": "business",
      "name": "Business",
      "price": 999,
      ...
    }
  ]
}
```

### GET /payments/subscription/current
Get current subscription.
```json
{
  "plan": "pro",
  "status": "active",
  "starts_at": "2024-01-01T00:00:00",
  "expires_at": "2024-02-01T00:00:00",
  "auto_renew": true
}
```

### POST /payments/subscription/cancel
Cancel subscription (keeps remaining days, stops auto-renew).
Requires: Bearer token

**Response:**
```json
{
  "status": "canceled",
  "plan": "pro",
  "remaining_days": 15,
  "expires_at": "2024-01-15T00:00:00",
  "message": "Подписка отменена. Доступ до 15 дней"
}
```

### POST /payments
Create payment.
```json
{
  "plan": "pro|business",
  "provider": "yookassa|yandex_pay"
}
```
Requires: Bearer token

**Response:**
```json
{
  "payment_id": "...",
  "confirmation_url": "https://..."
}
```

### GET /payments
Get payment history.
```json
{
  "payments": [
    { "id": "...", "plan": "pro", "amount": 299, "currency": "RUB", "status": "completed", "created_at": 1234567890 }
  ]
}
```

### GET /payments/{payment_id}
Get payment status.

### POST /payments/trial
Start PRO trial (7 days). Requires: Bearer token

### GET /payments/trial/status
Check trial status.

---

## Promocodes Routes (`/api/v1/promocodes`)

### POST /promocodes/redeem
Redeem promocode.
```json
{ "code": "PROMO20" }
```
Requires: Bearer token

**Response:**
```json
{
  "status": "ok",
  "plan": "pro",
  "expires_days": 30
}
```

### GET /promocodes (Admin only)
List all promocodes.

### POST /promocodes (Admin only)
Create promocode.
```json
{
  "code": "PROMO20",
  "plan": "pro|business",
  "duration_days": 30,
  "max_uses": 100,
  "expires_hours": 0  // 0 = no expiration
}
```

### DELETE /promocodes/{pc_id} (Admin only)
Delete promocode.

---

## Admin Routes (`/api/admin`)

All admin routes require: `role = admin|superadmin`

### GET /admin/stats
Dashboard statistics.
```json
{
  "total_users": 100,
  "active_users": 80,
  "total_links": 5000,
  "total_clicks": 100000,
  "links_today": 50,
  "clicks_today": 1000,
  "flagged_links": 5,
  "banned_links": 2
}
```

### GET /admin/users
List users with pagination and filters.
- Query: `?page=1&limit=50&search=john&plan=pro&role=admin`

### GET /admin/users/{user_id}
Get user details with links count, clicks, referrer, subscription.

### PUT /admin/users/{user_id}
Update user (plan, role, active status).
```json
{
  "plan": "pro",
  "role": "admin",
  "is_active": true
}
```

### DELETE /admin/users/{user_id}
Delete user.

### GET /admin/users/{user_id}/referrals
Get user's referrals.

### GET /admin/payments
List all payments.

### GET /admin/settings/ads
Get ad settings.

### PUT /admin/settings/ads
Update ad settings.

### GET /admin/settings
Get site settings.

### PUT /admin/settings
Update site settings.

---

## Import/Export Routes (`/api/v1/import-export`)

### GET /import-export/export/csv
Export links as CSV. Requires: Bearer token

### GET /import-export/export/json
Export links as JSON. Requires: Bearer token

### POST /import-export/import/csv
Import links from CSV. Requires: Bearer token
- Body: multipart/form-data with "file"

### POST /import-export/import/json
Import links from JSON. Requires: Bearer token
- Body: multipart/form-data with "file"

---

## Health Routes

### GET /health
Health check endpoint.

---

## Error Responses

All endpoints may return errors in format:
```json
{
  "detail": "Error message"
}
```

Common status codes:
- `400` - Bad Request
- `401` - Unauthorized
- `403` - Forbidden
- `404` - Not Found
- `409` - Conflict
- `429` - Too Many Requests
- `500` - Internal Server Error

---

## Rate Limiting

- **Registration**: 5 per hour per email
- **Anonymous links**: 10 per device
- **Authenticated**: Based on plan limits