"""
Event-window helper.

Reads configs/event_config.json once and exposes:

    get_event_window() -> (start_utc, end_utc)

start_utc is the `start_date` from the config, at 00:00 UTC.
end_utc   is exclusive: start_utc + duration_days.

If `start_date` is naive (YYYY-MM-DD), it is interpreted as midnight UTC.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache
from typing import Tuple

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "configs",
    "event_config.json",
)


@lru_cache(maxsize=1)
def _load_config() -> dict:
    with open(_CONFIG_PATH, "r") as f:
        return json.load(f)


def get_event_window() -> Tuple[datetime, datetime]:
    """
    Return (start_utc, end_utc_exclusive) for the current event.

    Reads start_date and cp.duration_days from configs/event_config.json.
    """
    cfg = _load_config()
    start_date = datetime.strptime(cfg["start_date"], "%Y-%m-%d").date()
    duration_days = int(cfg["cp"]["duration_days"])

    start_utc = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_utc = start_utc + timedelta(days=duration_days)
    return start_utc, end_utc


def get_event_branding() -> dict:
    """Return {'title': ..., 'subtitle': ...} from event_config.json.

    Used by the card renderer for the poster heading. Defaults are sensible
    if the keys are missing.
    """
    cfg = _load_config()
    b = cfg.get("branding") or {}
    return {
        "title": b.get("title", "25 Days of Productivity"),
        "subtitle": b.get("subtitle", "by The Programming Society"),
    }


def get_event_day_number(now: datetime | None = None) -> int | None:
    """
    Return the 1-indexed day number of the event for the given moment,
    or None if `now` is outside the event window.
    """
    start, end = get_event_window()
    now = now or datetime.now(timezone.utc)
    if now < start or now >= end:
        return None
    return (now.date() - start.date()).days + 1
