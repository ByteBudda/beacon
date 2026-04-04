# Beacon - URL Shortener SaaS

Professional URL shortener with analytics, QR codes, and more.

## Features

- 🔗 URL shortening with custom slugs
- 📊 Analytics (clicks, referrers, devices, countries)
- 📱 QR codes generation
- 🔐 Password protection
- 👥 Referral system
- 💳 Payment system (YooKassa, CryptoBot)
- 🤖 Telegram bot
- 📈 Admin panel

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run
python main.py
```

## Docker

```bash
docker-compose up -d
```

## Tech Stack

- Python 3.14+
- FastAPI
- SQLite/PostgreSQL
- Redis (optional)