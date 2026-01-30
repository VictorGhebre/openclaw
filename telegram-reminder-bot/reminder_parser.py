"""
Parse natural language reminder requests into (task, datetime) pairs.

Supports patterns like:
  - "remind me to check the deployment in 2 hours"
  - "remind me to call dentist tomorrow at 3pm"
  - "remind me buy groceries on friday"
  - "/remind 30m take a break"
  - "/remind 2h check CI"
"""

import re
from datetime import datetime, timedelta
from typing import Optional

import dateparser

from config import TIMEZONE

# ── Shorthand durations: "30m", "2h", "1d" ──────────────────────────────────

_SHORTHAND_RE = re.compile(
    r"^(\d+)\s*(m|min|mins|minutes?|h|hr|hrs|hours?|d|days?|w|weeks?)$",
    re.IGNORECASE,
)

_UNIT_MAP = {
    "m": "minutes", "min": "minutes", "mins": "minutes",
    "minute": "minutes", "minutes": "minutes",
    "h": "hours", "hr": "hours", "hrs": "hours",
    "hour": "hours", "hours": "hours",
    "d": "days", "day": "days", "days": "days",
    "w": "weeks", "week": "weeks", "weeks": "weeks",
}


def _parse_shorthand(text: str) -> Optional[datetime]:
    m = _SHORTHAND_RE.match(text.strip())
    if not m:
        return None
    amount = int(m.group(1))
    unit = _UNIT_MAP.get(m.group(2).lower())
    if not unit:
        return None
    return datetime.utcnow() + timedelta(**{unit: amount})


# ── Natural language: "in 2 hours", "tomorrow at 3pm", "friday" ─────────────

def _parse_natural(text: str) -> Optional[datetime]:
    result = dateparser.parse(
        text,
        settings={
            "TIMEZONE": TIMEZONE,
            "TO_TIMEZONE": "UTC",
            "RETURN_AS_TIMEZONE_AWARE": False,
            "PREFER_DATES_FROM": "future",
        },
    )
    return result


# ── Strip common prefixes ────────────────────────────────────────────────────

_PREFIX_RE = re.compile(
    r"^(?:remind\s+me\s+(?:to\s+)?)?",
    re.IGNORECASE,
)

# Separators between the task description and the time expression
_TIME_SEPARATORS = [
    " at ", " on ", " in ", " by ", " after ", " tomorrow", " next ",
]


def parse_reminder(text: str) -> Optional[tuple[str, datetime]]:
    """
    Parse a reminder string into (task_description, fire_at_utc).

    Returns None if parsing fails.
    """
    text = text.strip()
    if not text:
        return None

    # ── /remind shorthand: "/remind 30m take a break" ────────────────────
    slash_match = re.match(r"^/remind\s+(\S+)\s+(.*)", text, re.IGNORECASE | re.DOTALL)
    if slash_match:
        time_part = slash_match.group(1)
        task_part = slash_match.group(2).strip()
        fire_at = _parse_shorthand(time_part) or _parse_natural(time_part)
        if fire_at and task_part:
            return (task_part, fire_at)

    # ── Strip "remind me to ..." prefix ──────────────────────────────────
    body = _PREFIX_RE.sub("", text).strip()
    if not body:
        return None

    # Try splitting on time separators to isolate task vs. time
    for sep in _TIME_SEPARATORS:
        idx = body.lower().rfind(sep)
        if idx == -1:
            continue

        task_candidate = body[:idx].strip()
        time_candidate = body[idx:].strip()

        fire_at = _parse_natural(time_candidate)
        if fire_at and task_candidate:
            return (task_candidate, fire_at)

    # Fallback: try parsing the whole body as a time (unlikely but handles
    # edge cases like "remind me in 5 minutes" where the task is implicit)
    fire_at = _parse_natural(body)
    if fire_at:
        return ("(reminder)", fire_at)

    return None
