import time
import logging
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import config
from app.core.logging import setup_logging
from app.core.database import init_database, close_database
from app.core.rate_limiter import create_rate_limiter, rate_limiter as rl
import app.core.rate_limiter as rl_module
from app.core.security import validate_url
from app.services.admin_service import admin_service
from app.tasks import background_worker
from app.routers import auth, links, payments, admin
from app.routers import health, import_export, account, promocodes, settings
from app.routers.ad import router as ad_router
from utils.analytics import analytics

STATIC_DIR = Path(__file__).parent.parent / "static"
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(config.LOG_LEVEL, config.LOG_FORMAT)
    logger.info(f"Starting {config.APP_NAME} v3.1...")

    # Sentry
    if config.SENTRY_DSN:
        try:
            import sentry_sdk
            sentry_sdk.init(dsn=config.SENTRY_DSN, traces_sample_rate=0.1)
            logger.info("Sentry initialized")
        except ImportError:
            logger.warning("sentry-sdk not installed")

    await init_database(app)

    # Rate limiter
    rl_module.rate_limiter = create_rate_limiter()

    # Admin user
    try:
        await admin_service.create_admin_user(app.state.db)
    except Exception as e:
        logger.warning(f"Admin creation: {e}")

    # Telegram bot
    if config.telegram_enabled:
        try:
            if not config.TELEGRAM_BOT_TOKEN:
                logger.warning("Telegram bot token not configured")
            else:
                from app.bot.telegram_bot import telegram_bot
                await telegram_bot.start(app.state.db)
        except Exception as e:
            logger.warning(f"Telegram bot failed to start: {e}")

    # Background worker
    stop_event = asyncio.Event()
    worker_task = asyncio.create_task(background_worker(app.state.db, stop_event))

    yield

    logger.info("Shutting down...")
    stop_event.set()
    try:
        await asyncio.wait_for(worker_task, timeout=10)
    except asyncio.TimeoutError:
        worker_task.cancel()

    # Stop Telegram bot
    if config.telegram_enabled:
        try:
            from app.bot.telegram_bot import telegram_bot
            await telegram_bot.stop()
        except Exception:
            pass

    if rl_module.rate_limiter:
        await rl_module.rate_limiter.close()
    await close_database(app)


app = FastAPI(
    title=config.APP_NAME,
    version="3.1.0",
    description="Professional URL Shortener - Analytics, Payments, Admin",
    debug=config.DEBUG,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add CORS headers manually for Firefox
@app.middleware("http")
async def cors_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

if config.TRUSTED_HOSTS and config.TRUSTED_HOSTS != [""]:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.TRUSTED_HOSTS)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    ms = (time.time() - start) * 1000
    if not request.url.path.startswith("/static"):
        logger.info(f"{request.method} {request.url.path} {response.status_code} {ms:.0f}ms")
    return response


# Routers - API v1
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(links.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(import_export.router)
app.include_router(account.router)
app.include_router(promocodes.router)
app.include_router(settings.router)
app.include_router(ad_router)

app.include_router(auth.router, prefix="/api", tags=["auth-legacy"])
app.include_router(links.router, prefix="/api", tags=["links-legacy"])


# ========== PUBLIC ROUTES ==========

from jinja2 import Template

# Load SEO template at startup
SEO_TEMPLATE = None
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "index.html"
if TEMPLATE_PATH.exists():
    SEO_TEMPLATE = Template(TEMPLATE_PATH.read_text())

def is_bot(user_agent: str) -> bool:
    """Check if request is from a bot/crawler"""
    ua = user_agent.lower()
    bots = ["bot", "crawler", "spider", "facebook", "twitter", "telegram", "whatsapp", "vkshare", "discord", "yandex", "google", "bing", "yahoo", "duckduckgo", "applebot", "bingbot", "googlebot", "yandexbot", "twitterbot", "telegrambot"]
    return any(b in ua for b in bots)


@app.get("/")
async def index(request: Request):
    user_agent = request.headers.get("user-agent", "")
    if is_bot(user_agent) and SEO_TEMPLATE:
        return HTMLResponse(SEO_TEMPLATE.render(
            app_name=config.APP_NAME,
            app_url=config.APP_URL
        ))
    path = STATIC_DIR / "index.html"
    if path.exists():
        return HTMLResponse(path.read_text())
    return HTMLResponse(f'<html><head><title>{config.APP_NAME}</title></head><body style="font-family:Arial;text-align:center;padding:50px;background:#667eea;color:#fff"><h1>{config.APP_NAME}</h1><p><a href="/api-docs" style="color:#fff">API Docs</a></p></body></html>')


@app.get("/app", include_in_schema=False)
async def app_ui(request: Request):
    """Dashboard UI - uses existing working index.html"""
    path = STATIC_DIR / "index.html"
    if path.exists():
        return HTMLResponse(path.read_text())
    return HTMLResponse("Dashboard not found")


# ========== API DOCS ==========

@app.get("/docs", include_in_schema=False)
async def admin_docs(request: Request):
    """Full API docs - admin only"""
    from app.dependencies import get_current_user
    from fastapi import Depends
    
    try:
        auth = request.headers.get("authorization", "")
        if not auth.startswith("Bearer "):
            return HTMLResponse('<html><head><title>401 Unauthorized</title></head><body style="font-family:Arial;padding:50px;text-align:center"><h1>🔒 Требуется авторизация</h1><p>Войдите как админ для доступа к документации</p></body></html>', status_code=401)
        
        from app.dependencies import get_current_user_id
        try:
            user_id = await get_current_user_id(request)
            from app.dependencies import get_current_user
            user = await get_current_user(request, user_id)
            if user.get("role") not in ("admin", "superadmin"):
                return HTMLResponse('<html><head><title>403 Forbidden</title></head><body style="font-family:Arial;padding:50px;text-align:center"><h1>🔒 Только для админов</h1></body></html>', status_code=403)
        except Exception:
            return HTMLResponse('<html><head><title>401 Unauthorized</title></head><body style="font-family:Arial;padding:50px;text-align:center"><h1>🔒 Неверный токен</h1></body></html>', status_code=401)
        
        # Show full docs
        from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
        return get_swagger_ui_html(openapi_url="/openapi.json", title=f"{config.APP_NAME} - API Docs")
    except Exception as e:
        return HTMLResponse(f'<html><body>Error: {e}</body></html>', status_code=500)


@app.get("/api-docs", include_in_schema=False)
async def public_docs():
    """Public basic API docs"""
    from fastapi.openapi.docs import get_swagger_ui_html
    return get_swagger_ui_html(
        openapi_url="/openapi.json",
        title=f"{config.APP_NAME} - API",
        swagger_css_url="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css"
    )


@app.get("/openapi.json", include_in_schema=False)
async def openapi_json():
    """OpenAPI schema"""
    return app.openapi()


@app.get("/verify")
async def verify_page(token: str = None):
    if not token:
        return HTMLResponse('<html><body>Invalid link</body></html>', status_code=400)
    return RedirectResponse(url=f"/static/index.html?verify={token}")


@app.get("/s/{slug}")
async def redirect_link(slug: str, request: Request, password: str = None):
    """Redirect short link with OG tags for crawlers"""
    try:
        db = request.app.state.db
        cur = await db.execute("SELECT * FROM links WHERE slug = ?", (slug,))
        row = await cur.fetchone()

        if not row:
            raise HTTPException(404, "Link not found")

        cols = [d[0] for d in cur.description]
        link = dict(zip(cols, row))

        if not link.get("is_active", 1):
            raise HTTPException(404, "Link deactivated")

        if link["expires_at"] > 0 and time.time() > link["expires_at"]:
            raise HTTPException(410, "Link expired")

        # Blocked by moderation
        mod_status = link.get("moderation_status", "ok")
        if mod_status not in ("ok", "pending", ""):
            mod_reason = link.get("moderation_reason", "")
            return HTMLResponse(f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Link Blocked</title><style>
                body{{font-family:-apple-system,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#1a1a2e,#16213e);padding:20px}}
                .c{{background:#fff;border-radius:20px;padding:40px;max-width:500px;width:100%;text-align:center;box-shadow:0 20px 40px rgba(0,0,0,.2)}}
                .icon{{font-size:64px;margin-bottom:16px}}
                h2{{color:#c62828;margin-bottom:12px}}
                p{{color:#666;line-height:1.6}}
                .badge{{display:inline-block;padding:4px 12px;border-radius:6px;font-size:12px;font-weight:600;margin:16px 0 8px}}
                .badge-malware{{background:#ffebee;color:#c62828}}
                .badge-phishing{{background:#fff3e0;color:#e65100}}
                .badge-suspicious{{background:#fff8e1;color:#f57f17}}
                .badge-blacklisted{{background:#fce4ec;color:#880e4f}}
                a{{color:#0078d4}}
            </style></head><body><div class="c">
                <div class="icon">&#9888;&#65039;</div>
                <h2>Ссылка заблокирована</h2>
                <span class="badge badge-{mod_status}">{mod_status.upper()}</span>
                <p>{mod_reason}</p>
                <p style="margin-top:20px;font-size:13px">Эта ссылка была заблокирована системой модерации.<br>Если вы считаете, что это ошибка, свяжитесь с администрацией.</p>
            </div></body></html>''', status_code=403)

        # Password protection
        if link["is_password_protected"]:
            from app.core.security import verify_password
            if not password or not verify_password(password, link["password_hash"]):
                og = ""
                if link.get("og_title"):
                    og = f'<meta property="og:title" content="{link["og_title"]}">'
                if link.get("og_description"):
                    og += f'<meta property="og:description" content="{link["og_description"]}">'
                if link.get("og_image"):
                    og += f'<meta property="og:image" content="{link["og_image"]}">'
                return HTMLResponse(f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>Protected</title>{og}<style>
                    body{{font-family:-apple-system,sans-serif;min-height:100vh;display:flex;align-items:center;justify-content:center;background:linear-gradient(135deg,#667eea,#764ba2);padding:20px}}
                    .c{{background:#fff;border-radius:20px;padding:40px;max-width:400px;width:100%;text-align:center;box-shadow:0 20px 40px rgba(0,0,0,.1)}}
                    h2{{color:#333;margin-bottom:10px}}p{{color:#666;margin-bottom:30px}}
                    input{{width:100%;padding:12px;border:1px solid #ddd;border-radius:8px;font-size:16px;margin-bottom:15px}}
                    button{{width:100%;padding:12px;background:#0078d4;color:#fff;border:none;border-radius:8px;font-size:16px;cursor:pointer}}
                    .e{{color:#f44336;margin-top:10px}}
                </style></head><body><div class="c"><h2>Password Protected</h2><p>Enter password to access</p><form method="get"><input type="password" name="password" placeholder="Password" autofocus><button type="submit">Access</button>{'<div class="e">Wrong password</div>' if password else ''}</form></div></body></html>''', status_code=403 if password else 200)

        # OG meta for social crawlers
        ua = request.headers.get("user-agent", "").lower()
        is_crawler = any(bot in ua for bot in ["bot", "crawler", "spider", "facebook", "twitter", "telegram", "whatsapp", "vkshare", "discord"])
        if is_crawler and not link["is_password_protected"]:
            og = f'<meta property="og:url" content="{config.APP_URL}/s/{slug}">'
            og += f'<meta property="og:title" content="{link.get("og_title") or link.get("title") or slug}">'
            og += f'<meta property="og:description" content="{link.get("og_description") or link.get("description") or "Short link by QNTX.Beacon"}">'
            if link.get("og_image"):
                og += f'<meta property="og:image" content="{link["og_image"]}">'
            og += f'<meta http-equiv="refresh" content="0;url={link["url"]}">'
            return HTMLResponse(f'<html><head>{og}</head><body>Redirecting...</body></html>')

        # Record click and get country for geo-targeting
        ip = request.client.host if request.client else "unknown"
        ua_full = request.headers.get("user-agent", "")
        referer = request.headers.get("referer", "")
        click = analytics.process_click(ip, ua_full, referer)
        visitor_country = click.get("country", "XX")[:2] if click else "XX"

        # Geo-targeting redirect
        import json
        target_url = link["url"]
        geo_targets_str = link.get("geo_targets", "")
        if geo_targets_str:
            try:
                geo_targets = json.loads(geo_targets_str)
                if geo_targets and visitor_country in geo_targets:
                    target_url = geo_targets[visitor_country]
            except (json.JSONDecodeError, TypeError):
                pass
        
        # A/B testing - randomly choose from multiple URLs
        ab_urls_str = link.get("ab_urls", "")
        if ab_urls_str:
            try:
                ab_urls = json.loads(ab_urls_str)
                if ab_urls and isinstance(ab_urls, list) and len(ab_urls) > 0:
                    import random
                    target_url = random.choice(ab_urls)
            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        # Continue with click recording using existing click data
        await db.execute(
            "INSERT INTO clicks (link_id, ip, device_type, os, browser, referer, user_agent, country, ts) VALUES (?,?,?,?,?,?,?,?,?)",
            (link["id"], click.get("ip", ""), click.get("device_type", ""), click.get("os", ""),
             click.get("browser", ""), click.get("referer", ""), click.get("user_agent", ""), visitor_country, click.get("timestamp", "").timestamp())
        )
        await db.execute("UPDATE links SET clicks = clicks + 1 WHERE id = ?", (link["id"],))
        await db.commit()

        # Interstitial ad for free tier
        from app.services.ad_service import ad_service
        # Get link owner's plan
        cur = await db.execute("SELECT plan FROM users WHERE id = ?", (link["user_id"],))
        owner_row = await cur.fetchone()
        owner_plan = owner_row[0] if owner_row else "free"

        if await ad_service.should_show_ad(db, owner_plan):
            delay = await ad_service.get_delay(db)
            ad_html = await ad_service.get_ad_html(db)
            ad_title = await ad_service.get(db, "ad_title", "Подождите...")
            skip_text = await ad_service.get(db, "ad_skip_text", "Перейти к ссылке")
            target_url = link["url"]
            
            # Process ad HTML - just pass through, browser will render it
            processed_ad = ad_html

            return HTMLResponse(f'''<!DOCTYPE html><html><head><meta charset="UTF-8"><title>{ad_title}</title><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,sans-serif;min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;background:linear-gradient(135deg,#1a1a2e,#16213e);color:#fff;padding:20px}}
.ad-wrap{{max-width:600px;width:100%;text-align:center}}
.ad-title{{font-size:20px;margin-bottom:16px;opacity:.9}}
.ad-content{{background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.1);border-radius:16px;padding:24px;margin:20px 0;min-height:100px;display:flex;align-items:center;justify-content:center;overflow:hidden}}
.ad-content iframe{{border:none;border-radius:8px;max-width:100%}}
.timer{{font-size:48px;font-weight:700;color:#0078d4;margin:20px 0}}
.timer-label{{font-size:14px;opacity:.5;margin-bottom:20px}}
.btn-skip{{display:inline-block;padding:14px 32px;background:#0078d4;color:#fff;border:none;border-radius:10px;font-size:16px;font-weight:600;cursor:pointer;text-decoration:none;transition:all .3s;opacity:.4;pointer-events:none}}
.btn-skip.active{{opacity:1;pointer-events:auto}}
.btn-skip.active:hover{{background:#006abc;box-shadow:0 4px 16px rgba(0,120,212,.4)}}
.brand{{margin-top:40px;font-size:13px;opacity:.3}}
</style></head><body>
<div class="ad-wrap">
    <div class="ad-title">{ad_title}</div>
    <div class="ad-content" id="ad-content">
        {processed_ad if processed_ad else '<div style="opacity:.4">Рекламный блок</div>'}
    </div>
    <div class="timer" id="timer">{delay}</div>
    <div class="timer-label">секунд до перехода</div>
    <a class="btn-skip" id="btn-skip" href="{target_url}">{skip_text}</a>
    <div class="brand">QNTX.Beacon</div>
</div>
<script>
(function(){{
    var s={delay},el=document.getElementById('timer'),btn=document.getElementById('btn-skip');
    var iv=setInterval(function(){{
        s--;el.textContent=s;
        if(s<=0){{clearInterval(iv);btn.classList.add('active');el.textContent='✓';document.querySelector('.timer-label').textContent='Можно переходить';}}
    }},1000);
    setTimeout(function(){{window.location.href="{target_url}";}},({delay}+3)*1000);
}})();
</script>
</body></html>''')

        return RedirectResponse(url=link["url"], status_code=302)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Redirect error for {slug}: {e}")
        raise HTTPException(500)


# ========== STATIC FILES ==========

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ========== MAIN ==========

if __name__ == "__main__":
    import uvicorn
    warnings = config.validate()
    for w in warnings:
        logger.warning(w)

    uvicorn.run("app.main:app", host=config.SERVER_HOST, port=config.SERVER_PORT, reload=config.DEBUG)
