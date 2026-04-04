#!/usr/bin/env python3
"""
Beacon URL Shortener - Management CLI

Usage:
    python -m app.cli --help
    python -m app.cli user list
    python -m app.cli user create --username admin --email admin@example.com --password xxx
    python -m app.cli user reset-password --email user@example.com --password newpass
    python -m app.cli db migrate
    python -m app.cli health
"""

import asyncio
import argparse
import sys
import os
import time
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import config
from app.core.database import init_database, close_database
from app.core.security import hash_password, generate_api_key, hash_api_key
from app.services.admin_service import admin_service


class CLI:
    """Command-line interface for Beacon management"""

    def __init__(self):
        self.db = None
        self.parser = argparse.ArgumentParser(
            prog="beacon",
            description="Beacon URL Shortener Management CLI"
        )
        self.parser.add_argument("--debug", action="store_true", help="Debug mode")
        self._add_commands()

    def _add_commands(self):
        subparsers = self.parser.add_subparsers(dest="command", help="Available commands")

        # User commands
        user_parser = subparsers.add_parser("user", help="User management")
        user_sub = user_parser.add_subparsers(dest="subcommand", help="User subcommands")

        user_list = user_sub.add_parser("list", help="List users")
        user_list.add_argument("--limit", type=int, default=20, help="Limit results")
        user_list.add_argument("--plan", help="Filter by plan")

        user_create = user_sub.add_parser("create", help="Create user")
        user_create.add_argument("--username", required=True, help="Username")
        user_create.add_argument("--email", required=True, help="Email")
        user_create.add_argument("--password", required=True, help="Password")
        user_create.add_argument("--plan", default="free", choices=["free", "pro", "business"], help="Plan")
        user_create.add_argument("--role", default="user", choices=["user", "admin", "superadmin"], help="Role")

        user_reset = user_sub.add_parser("reset-password", help="Reset user password")
        user_reset.add_argument("--email", required=True, help="User email")
        user_reset.add_argument("--password", required=True, help="New password")

        user_delete = user_sub.add_parser("delete", help="Delete user")
        user_delete.add_argument("--email", required=True, help="User email")

        # Database commands
        db_parser = subparsers.add_parser("db", help="Database management")
        db_sub = db_parser.add_subparsers(dest="subcommand", help="Database subcommands")

        db_sub.add_parser("migrate", help="Run database migrations")
        db_sub.add_parser("status", help="Show database status")
        db_sub.add_parser("cleanup", help="Clean up old data")

        # Admin commands
        admin_parser = subparsers.add_parser("admin", help="Admin management")
        admin_sub = admin_parser.add_subparsers(dest="subcommand", help="Admin subcommands")

        admin_create = admin_sub.add_parser("create", help="Create admin user")
        admin_create.add_argument("--email", required=True, help="Admin email")
        admin_create.add_argument("--password", required=True, help="Admin password")

        # Stats commands
        subparsers.add_parser("stats", help="Show system statistics")

        # Health check
        subparsers.add_parser("health", help="Check system health")

        # Promo commands
        promo_parser = subparsers.add_parser("promo", help="Promocode management")
        promo_sub = promo_parser.add_subparsers(dest="subcommand", help="Promo subcommands")

        promo_create = promo_sub.add_parser("create", help="Create promocode")
        promo_create.add_argument("--code", required=True, help="Promo code")
        promo_create.add_argument("--plan", required=True, choices=["pro", "business"], help="Plan")
        promo_create.add_argument("--days", type=int, default=30, help="Duration in days")
        promo_create.add_argument("--max-uses", type=int, default=1, help="Max uses")

        promo_list = promo_sub.add_parser("list", help="List promocodes")

    async def run(self, args=None):
        parsed = self.parser.parse_args(args)
        
        if not parsed.command:
            self.parser.print_help()
            return

        # Initialize database
        class FakeApp:
            state = type('obj', (object,), {'db': None})()
        
        fake_app = FakeApp()
        
        # Create minimal async context
        await self._init_db(fake_app)
        
        try:
            if parsed.command == "user":
                await self._handle_user(parsed)
            elif parsed.command == "db":
                await self._handle_db(parsed)
            elif parsed.command == "admin":
                await self._handle_admin(parsed)
            elif parsed.command == "stats":
                await self._show_stats()
            elif parsed.command == "health":
                await self._show_health()
            elif parsed.command == "promo":
                await self._handle_promo(parsed)
        finally:
            await self._close_db(fake_app)

    async def _init_db(self, app):
        """Initialize database connection"""
        await init_database(app)
        self.db = app.state.db

    async def _close_db(self, app):
        """Close database connection"""
        if self.db:
            await self.db.close()

    async def _handle_user(self, args):
        """Handle user commands"""
        if args.subcommand == "list":
            limit = args.limit
            plan_filter = f" AND plan = '{args.plan}'" if args.plan else ""
            
            cur = await self.db.execute(
                f"SELECT id, username, email, plan, role, email_verified, is_active, created_at FROM users{plan_filter} ORDER BY id DESC LIMIT ?",
                (limit,)
            )
            rows = await cur.fetchall()
            
            print(f"\n{'ID':<4} {'Username':<20} {'Email':<30} {'Plan':<10} {'Role':<10} {'Verified':<10}")
            print("-" * 90)
            for r in rows:
                print(f"{r[0]:<4} {r[1]:<20} {r[2]:<30} {r[3]:<10} {r[4]:<10} {'Yes' if r[5] else 'No':<10}")
            print()

        elif args.subcommand == "create":
            now = time.time()
            pw_hash = hash_password(args.password)
            
            try:
                await self.db.execute(
                    "INSERT INTO users (username, email, password_hash, plan, role, email_verified, is_active, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
                    (args.username, args.email, pw_hash, args.plan, args.role, 1, 1, now, now)
                )
                await self.db.commit()
                print(f"User '{args.username}' created with plan '{args.plan}' and role '{args.role}'")
            except Exception as e:
                print(f"Error: {e}")

        elif args.subcommand == "reset-password":
            now = time.time()
            pw_hash = hash_password(args.password)
            
            await self.db.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE email = ?",
                (pw_hash, now, args.email)
            )
            await self.db.commit()
            print(f"Password updated for {args.email}")

        elif args.subcommand == "delete":
            await self.db.execute("DELETE FROM users WHERE email = ?", (args.email,))
            await self.db.commit()
            print(f"User {args.email} deleted")

    async def _handle_db(self, args):
        """Handle database commands"""
        if args.subcommand == "status":
            # Users count
            cur = await self.db.execute("SELECT COUNT(*) FROM users")
            users = (await cur.fetchone())[0]
            
            # Links count
            cur = await self.db.execute("SELECT COUNT(*) FROM links")
            links = (await cur.fetchone())[0]
            
            # Clicks count
            cur = await self.db.execute("SELECT COUNT(*) FROM clicks")
            clicks = (await cur.fetchone())[0]
            
            # Active subscriptions
            cur = await self.db.execute("SELECT COUNT(*) FROM subscriptions WHERE status = 'active'")
            subs = (await cur.fetchone())[0]
            
            print(f"\nDatabase Status:")
            print(f"  Users: {users}")
            print(f"  Links: {links}")
            print(f"  Clicks: {clicks}")
            print(f"  Active subscriptions: {subs}")
            print()

        elif args.subcommand == "cleanup":
            now = time.time()
            
            # Delete expired links
            cur = await self.db.execute("SELECT COUNT(*) FROM links WHERE expires_at > 0 AND expires_at < ?", (now,))
            expired_count = (await cur.fetchone())[0]
            
            await self.db.execute("DELETE FROM links WHERE expires_at > 0 AND expires_at < ?", (now,))
            
            # Delete old clicks (older than 90 days)
            old_ts = now - (90 * 86400)
            cur = await self.db.execute("SELECT COUNT(*) FROM clicks WHERE ts < ?", (old_ts,))
            old_clicks = (await cur.fetchone())[0]
            
            await self.db.execute("DELETE FROM clicks WHERE ts < ?", (old_ts,))
            
            await self.db.commit()
            
            print(f"Cleaned up:")
            print(f"  Expired links: {expired_count}")
            print(f"  Old clicks: {old_clicks}")

    async def _handle_admin(self, args):
        """Handle admin commands"""
        if args.subcommand == "create":
            result = await admin_service.create_admin_user(self.db, args.email, args.password)
            print(f"Admin created: {result}")

    async def _show_stats(self):
        """Show system statistics"""
        cur = await self.db.execute("SELECT COUNT(*) FROM users")
        users = (await cur.fetchone())[0]
        
        cur = await self.db.execute("SELECT COUNT(*) FROM links")
        links = (await cur.fetchone())[0]
        
        cur = await self.db.execute("SELECT SUM(clicks) FROM links")
        clicks = (await cur.fetchone())[0] or 0
        
        cur = await self.db.execute("SELECT COUNT(*) FROM users WHERE plan != 'free'")
        paid = (await cur.fetchone())[0]
        
        print(f"\n=== Beacon Statistics ===")
        print(f"Users: {users}")
        print(f"  - Paid: {paid}")
        print(f"  - Free: {users - paid}")
        print(f"Links: {links}")
        print(f"Clicks: {clicks}")
        print()

    async def _show_health(self):
        """Check system health"""
        print("\n=== Health Check ===")
        
        # Database
        try:
            await self.db.execute("SELECT 1")
            print("[OK] Database")
        except Exception as e:
            print(f"[FAIL] Database: {e}")
        
        print()

    async def _handle_promo(self, args):
        """Handle promo commands"""
        now = time.time()
        
        if args.subcommand == "create":
            await self.db.execute(
                "INSERT INTO promocodes (code, plan, duration_days, max_uses, is_active, created_at) VALUES (?,?,?,?,?,?)",
                (args.code.upper(), args.plan, args.days, args.max_uses, 1, now)
            )
            await self.db.commit()
            print(f"Promocode '{args.code}' created for plan '{args.plan}', {args.days} days")
        
        elif args.subcommand == "list":
            cur = await self.db.execute("SELECT code, plan, duration_days, max_uses, used_count, is_active FROM promocodes")
            rows = await cur.fetchall()
            
            print(f"\n{'Code':<15} {'Plan':<10} {'Days':<6} {'Max':<6} {'Used':<6} {'Active':<8}")
            print("-" * 55)
            for r in rows:
                print(f"{r[0]:<15} {r[1]:<10} {r[2]:<6} {r[3]:<6} {r[4]:<6} {'Yes' if r[5] else 'No':<8}")
            print()


def main():
    cli = CLI()
    asyncio.run(cli.run())


if __name__ == "__main__":
    main()