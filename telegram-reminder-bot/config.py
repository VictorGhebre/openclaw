import os

# Telegram bot token from @BotFather
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

# Your Telegram user ID — only this user can interact with the bot.
# Find yours by messaging @userinfobot on Telegram.
ALLOWED_USER_ID = int(os.environ.get("TELEGRAM_USER_ID", "0"))

# Timezone for interpreting relative times like "tomorrow at 3pm"
TIMEZONE = os.environ.get("BOT_TIMEZONE", "UTC")

# SQLite database path
DB_PATH = os.environ.get("BOT_DB_PATH", os.path.join(os.path.dirname(__file__), "reminders.db"))
