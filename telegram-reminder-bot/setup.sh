#!/usr/bin/env bash
set -euo pipefail

# ── Telegram Reminder Bot — Setup Script ─────────────────────────────────────
#
# Usage:
#   1. Create a bot via @BotFather on Telegram and copy the token
#   2. Get your Telegram user ID from @userinfobot
#   3. Run: ./setup.sh
#
# This script:
#   - Creates a Python venv and installs dependencies
#   - Prompts for your bot token and user ID
#   - Generates a .env file
#   - Installs a systemd service so the bot starts on boot
# ──────────────────────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Telegram Reminder Bot Setup ==="
echo ""

# ── 1. Python venv ───────────────────────────────────────────────────────────

if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "Installing dependencies..."
venv/bin/pip install --quiet --upgrade pip
venv/bin/pip install --quiet -r requirements.txt
echo "Dependencies installed."
echo ""

# ── 2. Configuration ────────────────────────────────────────────────────────

if [ -f ".env" ]; then
    echo ".env already exists. Skipping configuration prompts."
    echo "Edit .env manually to change settings."
else
    read -rp "Telegram Bot Token (from @BotFather): " BOT_TOKEN
    read -rp "Your Telegram User ID (from @userinfobot): " USER_ID
    read -rp "Timezone [UTC]: " TIMEZONE
    TIMEZONE="${TIMEZONE:-UTC}"

    cat > .env <<EOF
TELEGRAM_BOT_TOKEN=${BOT_TOKEN}
TELEGRAM_USER_ID=${USER_ID}
BOT_TIMEZONE=${TIMEZONE}
EOF
    echo "Saved .env"
fi

echo ""

# ── 3. systemd service ──────────────────────────────────────────────────────

SERVICE_NAME="reminder-bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "Setting up systemd service..."

# Generate the service file with actual paths
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Telegram Reminder Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=${SCRIPT_DIR}
EnvironmentFile=${SCRIPT_DIR}/.env
ExecStart=${SCRIPT_DIR}/venv/bin/python bot.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo ""
echo "=== Setup complete ==="
echo ""
echo "The bot is now running as a systemd service."
echo ""
echo "Useful commands:"
echo "  sudo systemctl status reminder-bot    # check status"
echo "  sudo journalctl -u reminder-bot -f    # follow logs"
echo "  sudo systemctl restart reminder-bot   # restart"
echo "  sudo systemctl stop reminder-bot      # stop"
echo ""
echo "Open Telegram and message your bot to get started!"
