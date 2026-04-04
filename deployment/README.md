#Deployment Guide

## Quick Start (Docker)

### 1. Clone and configure
```bash
git clone <repo-url> beaconqntx
cd beaconqntx
cp .env .env.production
nano .env.production  # Edit settings
```

### 2. Key settings (.env.production)
```bash
DEBUG=false
APP_URL=https://your-domain.com
DEFAULT_DOMAIN=your-domain.com
JWT_SECRET=<generate-secure-random-string>
SMTP_HOST=smtp.your-provider.com
SMTP_PORT=465
SMTP_USER=your-email
SMTP_PASSWORD=your-password
FROM_EMAIL=your-email@domain.com
YOOKASSA_SHOP_ID=<shop-id>
YOOKASSA_SECRET_KEY=<secret-key>
TELEGRAM_BOT_TOKEN=<bot-token>
```

### 3. Build and run
```bash
docker build -t beacon .
docker run -d -p 3333:3333 --env-file .env.production -v ./data:/app/data beacon
```

### 4. With Nginx reverse proxy
```bash
# Using docker-compose.simple.yml
cp deployment/docker-compose.simple.yml docker-compose.yml
cp deployment/nginx.conf nginx.conf
docker-compose up -d
```

## Production Checklist

- [ ] Set `DEBUG=false`
- [ ] Generate strong `JWT_SECRET` (64+ random chars)
- [ ] Configure SMTP for emails
- [ ] Set correct `APP_URL` and `DEFAULT_DOMAIN`
- [ ] Configure payment gateway keys
- [ ] Set `ADMIN_EMAIL` for admin access
- [ ] Enable SSL/HTTPS
- [ ] Set up backup for `./data/` folder

## Server Requirements
- 1+ CPU core
- 1GB+ RAM
- 10GB+ SSD storage
- Domain with DNS configured

## Manual Deployment (no Docker)

```bash
# Install Python 3.12
apt update && apt install -y python3.12 python3.12-venv python3-pip curl

# Create venv
python3.12 -m venv venv
source venv/bin/activate

# Install
pip install -r requirements.txt

# Run
python -m uvicorn app.main:app --host 0.0.0.0 --port 3333
```

## Backup
```bash
# Daily backup cron
0 2 * * * tar -czf /backup/beacon-$(date +\%Y\%m\%d).tar.gz -C /home/user beaconqntx/data
```