"""APScheduler wrapper — schedules reminder jobs and fires them via Telegram."""

import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger

import storage

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
_send_callback = None  # async fn(text: str) -> None


def init(send_callback) -> AsyncIOScheduler:
    """
    Initialize the scheduler.

    send_callback: an async function that sends a message to the user.
                   Signature: async def send(text: str) -> None
    """
    global _scheduler, _send_callback
    _send_callback = send_callback
    _scheduler = AsyncIOScheduler()
    _scheduler.start()
    _reload_pending()
    return _scheduler


def schedule_reminder(reminder_id: int, task: str, fire_at: datetime) -> None:
    """Add a one-shot job that fires at the given UTC datetime."""
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized — call init() first")

    job_id = f"reminder_{reminder_id}"
    _scheduler.add_job(
        _fire_reminder,
        trigger=DateTrigger(run_date=fire_at),
        id=job_id,
        replace_existing=True,
        kwargs={"reminder_id": reminder_id, "task": task},
    )
    logger.info("Scheduled reminder #%d for %s: %s", reminder_id, fire_at, task)


def cancel_reminder(reminder_id: int) -> None:
    """Remove a scheduled job if it exists."""
    if _scheduler is None:
        return
    job_id = f"reminder_{reminder_id}"
    try:
        _scheduler.remove_job(job_id)
    except Exception:
        pass  # already fired or never scheduled


async def _fire_reminder(reminder_id: int, task: str) -> None:
    """Called by APScheduler when a reminder is due."""
    storage.mark_fired(reminder_id)
    msg = f"Reminder #{reminder_id}: {task}"
    logger.info("Firing: %s", msg)
    if _send_callback:
        try:
            await _send_callback(msg)
        except Exception:
            logger.exception("Failed to send reminder #%d", reminder_id)


def _reload_pending() -> None:
    """Reload all unfired reminders from the DB (e.g. after a restart)."""
    for r in storage.get_all_unfired():
        fire_at = datetime.fromisoformat(r["fire_at"])
        if fire_at <= datetime.utcnow():
            # Overdue — fire immediately
            import asyncio
            asyncio.ensure_future(
                _fire_reminder(reminder_id=r["id"], task=r["task"])
            )
        else:
            schedule_reminder(r["id"], r["task"], fire_at)
