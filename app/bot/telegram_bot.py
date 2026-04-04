import logging
import re
import asyncio
from urllib.parse import urlparse

from app.core.config import config
from app.core.security import hash_password, generate_api_key, hash_api_key
from app.services.link_checker import check_url

logger = logging.getLogger(__name__)

LINK_RE = re.compile(r'https?://[^\s<>"\']+')
SLUG_RE = re.compile(r'^[a-zA-Z0-9_-]{3,30}$')


def _is_url(text: str) -> bool:
    return bool(LINK_RE.match(text.strip()))


def _escape_md(text: str) -> str:
    """Escape markdown special chars"""
    for c in ['_', '*', '`', '[']:
        text = text.replace(c, '\\' + c)
    return text


class TelegramBot:
    """QNTX.Beacon Telegram Bot"""

    def __init__(self):
        self._app = None
        self._db = None

    async def start(self, db):
        """Start the bot"""
        try:
            from telegram import Update, BotCommand
            from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
        except ImportError:
            logger.warning("python-telegram-bot not installed, bot disabled")
            return

        if not config.telegram_enabled:
            logger.info("Telegram bot not configured")
            return

        self._db = db

        app = Application.builder().token(config.TELEGRAM_BOT_TOKEN).build()

        # Commands
        app.add_handler(CommandHandler("start", self._cmd_start))
        app.add_handler(CommandHandler("help", self._cmd_help))
        app.add_handler(CommandHandler("short", self._cmd_short))
        app.add_handler(CommandHandler("my", self._cmd_my_links))
        app.add_handler(CommandHandler("stats", self._cmd_stats))
        app.add_handler(CommandHandler("delete", self._cmd_delete))
        app.add_handler(CommandHandler("qr", self._cmd_qr))

        # Message handler for auto-detecting URLs
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._on_message))

        # Set bot commands
        await app.bot.set_my_commands([
            BotCommand("start", "Начать работу"),
            BotCommand("short", "Сократить ссылку: /short https://example.com"),
            BotCommand("my", "Мои ссылки"),
            BotCommand("stats", "Статистика: /stats slug"),
            BotCommand("delete", "Удалить: /delete slug"),
            BotCommand("qr", "QR-код: /qr slug"),
            BotCommand("help", "Помощь"),
        ])

        self._app = app
        logger.info(f"Telegram bot started: @{config.TELEGRAM_BOT_USERNAME}")

        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)

    async def stop(self):
        if self._app:
            await self._app.updater.stop()
            await self._app.stop()
            await self._app.shutdown()

    # ========== HANDLERS ==========

    async def _cmd_start(self, update, context):
        text = (
            "👋 *QNTX.Beacon Bot*\n\n"
            "Отправьте мне ссылку — я сокращу её!\n\n"
            "Команды:\n"
            "/short URL — создать ссылку\n"
            "/my — мои последние ссылки\n"
            "/stats slug — статистика\n"
            "/qr slug — QR-код\n"
            "/delete slug — удалить\n"
            "/help — помощь"
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    async def _cmd_help(self, update, context):
        text = (
            "*Как пользоваться:*\n\n"
            "1️⃣ Отправьте URL прямо в чат — получите короткую ссылку\n"
            "2️⃣ Или используйте /short https://example.com\n"
            "3️⃣ Для кастомного алиаса: /short https://example.com my-alias\n\n"
            "*Команды:*\n"
            "/short URL [alias] — создать\n"
            "/my — последние 10 ссылок\n"
            "/stats slug — клики, устройства, браузеры\n"
            "/qr slug — QR-код\n"
            "/delete slug — удалить\n\n"
            f"🌐 {config.APP_URL}"
        )
        await update.message.reply_text(text, parse_mode="Markdown")

    async def _cmd_short(self, update, context):
        args = context.args
        if not args:
            await update.message.reply_text("Использование: /short URL [alias]")
            return

        url = args[0].strip()
        alias = args[1].strip() if len(args) > 1 else ""

        if not _is_url(url):
            await update.message.reply_text("❌ Некорректный URL")
            return

        await self._create_link(update, url, alias)

    async def _on_message(self, update, context):
        """Auto-detect URLs in messages"""
        text = update.message.text or ""
        urls = LINK_RE.findall(text)

        if not urls:
            await update.message.reply_text(
                "Отправьте ссылку для сокращения или используйте /help"
            )
            return

        # Check for "url alias" format
        parts = text.strip().split()
        url = parts[0]
        alias = parts[1] if len(parts) > 1 else ""

        if _is_url(url):
            await self._create_link(update, url, alias)
        else:
            await update.message.reply_text("❌ Не удалось распознать URL")

    async def _cmd_my_links(self, update, context):
        """Show user's recent links"""
        tg_id = str(update.effective_user.id)
        db = self._db

        # Find or create user by telegram_id stored in verification_token field
        cur = await db.execute(
            "SELECT id FROM users WHERE verification_token = ?",
            (f"tg:{tg_id}",)
        )
        row = await cur.fetchone()

        if not row:
            await update.message.reply_text(
                "Вы ещё не создавали ссылок. Просто отправьте URL!"
            )
            return

        user_id = row[0]
        cur = await db.execute(
            "SELECT slug, url, clicks, created_at FROM links WHERE user_id = ? ORDER BY created_at DESC LIMIT 10",
            (user_id,)
        )
        rows = await cur.fetchall()

        if not rows:
            await update.message.reply_text("У вас пока нет ссылок.")
            return

        lines = []
        for slug, url, clicks, ts in rows:
            short = f"{config.APP_URL}/s/{slug}"
            lines.append(f"🔗 `{slug}` — {clicks} кликов\n   {_escape_md(url[:50])}")

        await update.message.reply_text(
            "*Ваши последние ссылки:*\n\n" + "\n\n".join(lines),
            parse_mode="Markdown"
        )

    async def _cmd_stats(self, update, context):
        """Show link stats"""
        args = context.args
        if not args:
            await update.message.reply_text("Использование: /stats slug")
            return

        slug = args[0].strip()
        db = self._db

        cur = await db.execute("SELECT id, clicks, url FROM links WHERE slug = ?", (slug,))
        row = await cur.fetchone()
        if not row:
            await update.message.reply_text("❌ Ссылка не найдена")
            return

        link_id, clicks, url = row

        # Device stats
        cur = await db.execute(
            "SELECT device_type, COUNT(*) FROM clicks WHERE link_id = ? GROUP BY device_type",
            (link_id,)
        )
        devices = {r[0] or "unknown": r[1] for r in await cur.fetchall()}

        # Browser stats
        cur = await db.execute(
            "SELECT browser, COUNT(*) FROM clicks WHERE link_id = ? GROUP BY browser ORDER BY COUNT(*) DESC LIMIT 5",
            (link_id,)
        )
        browsers = {r[0] or "unknown": r[1] for r in await cur.fetchall()}

        text = (
            f"*Статистика:* `{slug}`\n\n"
            f"🔗 {_escape_md(url[:60])}\n"
            f"👆 Всего кликов: *{clicks}*\n\n"
        )

        if devices:
            text += "*Устройства:*\n"
            for d, c in devices.items():
                text += f"  {d}: {c}\n"

        if browsers:
            text += "\n*Браузеры:*\n"
            for b, c in browsers.items():
                text += f"  {b}: {c}\n"

        await update.message.reply_text(text, parse_mode="Markdown")

    async def _cmd_delete(self, update, context):
        """Delete a link"""
        args = context.args
        if not args:
            await update.message.reply_text("Использование: /delete slug")
            return

        slug = args[0].strip()
        tg_id = str(update.effective_user.id)
        db = self._db

        cur = await db.execute(
            "SELECT l.id FROM links l JOIN users u ON l.user_id = u.id WHERE l.slug = ? AND u.verification_token = ?",
            (slug, f"tg:{tg_id}")
        )
        row = await cur.fetchone()

        if not row:
            await update.message.reply_text("❌ Ссылка не найдена или не ваша")
            return

        await db.execute("DELETE FROM clicks WHERE link_id = ?", (row[0],))
        await db.execute("DELETE FROM links WHERE id = ?", (row[0],))
        await db.commit()

        await update.message.reply_text(f"✅ Ссылка `{slug}` удалена", parse_mode="Markdown")

    async def _cmd_qr(self, update, context):
        """Send QR code"""
        args = context.args
        if not args:
            await update.message.reply_text("Использование: /qr slug")
            return

        slug = args[0].strip()
        from utils.qr_generator import qr_generator
        from io import BytesIO

        url = f"{config.APP_URL}/s/{slug}"
        qr_data = qr_generator.generate_qr_code(slug)

        if qr_data and qr_data.startswith("data:image"):
            import base64
            img_bytes = base64.b64decode(qr_data.split(",")[1])
            await update.message.reply_photo(
                photo=BytesIO(img_bytes),
                caption=f"QR для `{slug}`\n{url}",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(f"🔗 {url}")

    # ========== HELPERS ==========

    async def _create_link(self, update, url: str, alias: str = ""):
        """Create a short link"""
        db = self._db
        tg_id = str(update.effective_user.id)
        tg_username = update.effective_user.username or f"tg_{tg_id}"

        # SSRF check
        from app.core.security import validate_url
        valid, err = validate_url(url)
        if not valid:
            await update.message.reply_text(f"❌ {err}")
            return

        # Find or create user for this telegram
        cur = await db.execute("SELECT id FROM users WHERE verification_token = ?", (f"tg:{tg_id}",))
        row = await cur.fetchone()

        if row:
            user_id = row[0]
        else:
            # Create bot user
            import time, secrets
            now = time.time()
            password = secrets.token_hex(16)
            from app.core.security import hash_password
            await db.execute(
                """INSERT INTO users (username, email, password_hash, plan, email_verified, verification_token, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (f"tg_{tg_username}", f"tg_{tg_id}@telegram.bot", hash_password(password),
                 "free", 1, f"tg:{tg_id}", now, now)
            )
            await db.commit()
            cur = await db.execute("SELECT id FROM users WHERE verification_token = ?", (f"tg:{tg_id}",))
            user_id = (await cur.fetchone())[0]

        # Check plan limit
        cur = await db.execute("SELECT plan FROM users WHERE id = ?", (user_id,))
        plan = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM links WHERE user_id = ?", (user_id,))
        count = (await cur.fetchone())[0]

        from app.core.config import config
        if count >= config.PLAN_LIMITS.get(plan, 50):
            await update.message.reply_text(
                f"❌ Лимит ссылок исчерпан ({config.PLAN_LIMITS.get(plan, 50)}).\n"
                f"Обновите тариф: {config.APP_URL}"
            )
            return

        # Generate slug
        import random, string, time
        slug = alias or ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        now = time.time()

        if SLUG_RE.match(slug):
            cur = await db.execute("SELECT id FROM links WHERE slug = ?", (slug,))
            if await cur.fetchone():
                if alias:
                    await update.message.reply_text(f"❌ Алиас `{slug}` уже занят", parse_mode="Markdown")
                    return
                slug = ''.join(random.choices(string.ascii_letters + string.digits, k=8))

        # Moderation check
        mod_status = "ok"
        if config.MODERATION_ENABLED:
            result = await check_url(url)
            if not result["safe"]:
                await update.message.reply_text(
                    f"❌ Ссылка заблокирована: {result['reason']}"
                )
                return

        # Create link
        await db.execute(
            "INSERT INTO links (user_id, slug, url, created_at, moderation_status) VALUES (?,?,?,?,?)",
            (user_id, slug, url, now, mod_status)
        )
        await db.commit()

        short_url = f"{config.APP_URL}/s/{slug}"
        await update.message.reply_text(
            f"✅ *Готово!*\n\n"
            f"🔗 `{short_url}`\n"
            f"📎 {_escape_md(url[:80])}",
            parse_mode="Markdown",
            disable_web_page_preview=True
        )


# Singleton
telegram_bot = TelegramBot()
