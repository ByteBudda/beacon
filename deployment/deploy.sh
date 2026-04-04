#!/bin/bash
# Deploy script for qntx.ru

set -e

echo "=== QNTX.Beacon Deployment ==="

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Run as root or use sudo"
    exit 1
fi

# Update .env with production settings
echo "Configuring production environment..."
cd /home/alex/Загрузки/beaconqntx

# Create data directory
mkdir -p data logs

# Set permissions
chown -R alex:alex data logs
chmod 755 data logs

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3.12 -m venv venv
fi

echo "Installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt --quiet

# Generate JWT_SECRET if not set
if ! grep -q "JWT_SECRET=" .env || grep "JWT_SECRET=" .env | grep -q "CHANGE_ME"; then
    JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/JWT_SECRET=.*/JWT_SECRET=$JWT_SECRET/" .env
fi

# Update app URL
sed -i "s|APP_URL=.*|APP_URL=https://qntx.ru|" .env
sed -i "s|DEFAULT_DOMAIN=.*|DEFAULT_DOMAIN=qntx.ru|" .env
sed -i "s|DEBUG=.*|DEBUG=false|" .env

echo "Starting application..."
source venv/bin/activate

# Start with systemd or directly
if command -v systemctl &> /dev/null; then
    # Create systemd service
    cat > /etc/systemd/system/beacon.service << EOF
[Unit]
Description=QNTX.Beacon URL Shortener
After=network.target

[Service]
Type=simple
User=alex
WorkingDirectory=/home/alex/Загрузки/beaconqntx
ExecStart=/home/alex/Загрузки/beaconqntx/venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 3333
Restart=always
RestartSec=10
Environment="PATH=/home/alex/Загрузки/beaconqntx/venv/bin"

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable beacon
    systemctl restart beacon
    echo "Service started: systemctl status beacon"
else
    # Run directly with nohup
    nohup python -m uvicorn app.main:app --host 0.0.0.0 --port 3333 > logs/beacon.log 2>&1 &
    echo "Application started on port 3333"
fi

echo "=== Deployment Complete ==="
echo "URL: https://qntx.ru:3333"