#!/usr/bin/env python3
"""
Telegram Reminder Bot — a lightweight, always-on personal assistant.

Zero API costs. No LLM required. Runs on any VPS.

Commands:
  /start              — Welcome message
  /help               — Show available commands
  /remind <dur> <msg> — Quick reminder ("/remind 30m stretch")
  /list               — List pending reminders
  /cancel <id>        — Cancel a reminder

Natural language:
  "remind me to check CI in 2 hours"
  "remind me to call dentist tomorrow at 3pm"
"""

import logging
import sys
from datetime import datetime

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import config
import scheduler
import storage
from reminder_parser import parse_reminder

logging.basicConfig(
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("bot")


# ── Auth guard ────────────────────────────────────────────────────────────────

def _authorized(update: Update) -> bool:
    """Only allow the configured user to interact with the bot."""
    if config.ALLOWED_USER_ID == 0:
        return True  # no restriction configured
    return update.effective_user and update.effective_user.id == config.ALLOWED_USER_ID


# ── Command handlers ─────────────────────────────────────────────────────────

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    await update.message.reply_text(
        "Hey! I'm your reminder bot.\n\n"
        "Just type something like:\n"
        '  "remind me to check the deployment in 2 hours"\n\n'
        "Or use /help to see all commands."
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return
    await update.message.reply_text(
        "Commands:\n"
        "  /remind <duration> <task>\n"
        "    e.g. /remind 30m take a break\n"
        "    e.g. /remind 2h check CI pipeline\n\n"
        "  /list — show pending reminders\n"
        "  /cancel <id> — cancel a reminder\n\n"
        "Natural language:\n"
        '  "remind me to call dentist tomorrow at 3pm"\n'
        '  "remind me to review PR in 45 minutes"'
    )


async def cmd_remind(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /remind <shorthand> <task>."""
    if not _authorized(update):
        return

    text = update.message.text or ""
    result = parse_reminder(text)
    if not result:
        await update.message.reply_text(
            "Couldn't parse that. Try:\n"
            "  /remind 30m take a break\n"
            "  /remind 2h check CI"
        )
        return

    task, fire_at = result
    reminder_id = storage.add_reminder(task, fire_at)
    scheduler.schedule_reminder(reminder_id, task, fire_at)

    await update.message.reply_text(
        f"Reminder #{reminder_id} set.\n"
        f"Task: {task}\n"
        f"When: {fire_at.strftime('%Y-%m-%d %H:%M UTC')}"
    )


async def cmd_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return

    pending = storage.list_pending()
    if not pending:
        await update.message.reply_text("No pending reminders.")
        return

    lines = []
    for r in pending:
        fire_at = datetime.fromisoformat(r["fire_at"]).strftime("%Y-%m-%d %H:%M UTC")
        lines.append(f"  #{r['id']}  {fire_at}  —  {r['task']}")

    await update.message.reply_text("Pending reminders:\n" + "\n".join(lines))


async def cmd_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    if not _authorized(update):
        return

    text = (update.message.text or "").strip()
    parts = text.split()
    if len(parts) < 2 or not parts[1].lstrip("#").isdigit():
        await update.message.reply_text("Usage: /cancel <id>  (e.g. /cancel 3)")
        return

    reminder_id = int(parts[1].lstrip("#"))
    deleted = storage.delete_reminder(reminder_id)
    if deleted:
        scheduler.cancel_reminder(reminder_id)
        await update.message.reply_text(f"Reminder #{reminder_id} cancelled.")
    else:
        await update.message.reply_text(f"Reminder #{reminder_id} not found.")


# ── Natural language handler ─────────────────────────────────────────────────

async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Catch-all for non-command messages — tries to parse as a reminder."""
    if not _authorized(update):
        return

    text = (update.message.text or "").strip()
    if not text:
        return

    # Only attempt parsing if it looks like a reminder request
    lower = text.lower()
    if not any(lower.startswith(p) for p in ("remind me", "reminder", "set a reminder")):
        await update.message.reply_text(
            "I only handle reminders for now. Try:\n"
            '  "remind me to check CI in 2 hours"\n'
            "  /help for all commands"
        )
        return

    result = parse_reminder(text)
    if not result:
        await update.message.reply_text(
            "I understood you want a reminder, but couldn't parse the time.\n"
            "Try: remind me to <task> in <duration>\n"
            "  e.g. remind me to stretch in 30 minutes"
        )
        return

    task, fire_at = result
    reminder_id = storage.add_reminder(task, fire_at)
    scheduler.schedule_reminder(reminder_id, task, fire_at)

    await update.message.reply_text(
        f"Reminder #{reminder_id} set.\n"
        f"Task: {task}\n"
        f"When: {fire_at.strftime('%Y-%m-%d %H:%M UTC')}"
    )


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    if not config.BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set. Export it and try again.")
        sys.exit(1)

    app = Application.builder().token(config.BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("remind", cmd_remind))
    app.add_handler(CommandHandler("list", cmd_list))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Set up proactive message sender — scheduler uses this to ping you
    async def send_to_owner(text: str) -> None:
        await app.bot.send_message(chat_id=config.ALLOWED_USER_ID, text=text)

    # Post-init: start scheduler after the bot event loop is running
    async def post_init(application: Application) -> None:
        scheduler.init(send_to_owner)
        logger.info("Bot started. Scheduler loaded.")

    app.post_init = post_init

    logger.info("Starting bot... (polling)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
