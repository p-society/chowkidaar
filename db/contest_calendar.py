"""
Global contest calendar — gating layer for per-user contest polls.

The /submit handler used to call the LC + CF *user* APIs on every single
submission, paying ≥3s of HTTP latency (LC: 1s rate limit + CF: 2s rate
limit) even on quiet days. This module fixes that:

    /submit → any_contest_between(last_user_poll, now)?
              │
              ├── yes → run the existing per-user poll
              └── no  → skip; nothing could have changed

The cache holds the global LC + CF contest schedules with a 5-minute TTL —
cheap to keep warm, fresh enough that we never miss a contest that just
ended. A 3-hour grace period is added to each contest's end time to absorb
Codeforces' rating-update lag (CF can take 1–3 hours after a round to push
rating data; we don't want to gate-out before that's available).

Fail-open: if both upstream schedule APIs fail, `any_contest_between`
returns True so the per-user poll runs anyway. We'd rather over-poll than
silently miss a points award.

Thread-safe: the refresh is guarded by a lock so concurrent /submit
handlers don't all stampede the upstream APIs at the same time.

Public surface:
    any_contest_between(t1, t2) -> bool
        Did any LC or CF contest's (end_time + grace) fall in (t1, t2]?
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from integrations.contest_schedule import (
    ContestSchedule,
    ContestScheduleError,
    fetch_codeforces_schedule,
    fetch_leetcode_schedule,
)

# How long a cached schedule is considered fresh.
_CACHE_TTL = timedelta(minutes=5)

# After a contest ends, the rating/ranking data can take a while to
# propagate (CF is the worst offender). We keep the gate "open" for this
# long after each contest's end so the user-poll can catch late data.
_RATING_GRACE = timedelta(hours=3)

_lock = threading.Lock()
_cache: List[ContestSchedule] = []
_cache_loaded_at: Optional[datetime] = None
_last_load_failed: bool = False


def _refresh_if_stale() -> None:
    """Repopulate the cache from upstream if it's missing or stale."""
    global _cache, _cache_loaded_at, _last_load_failed
    now = datetime.now(timezone.utc)
    with _lock:
        if _cache_loaded_at is not None and (now - _cache_loaded_at) < _CACHE_TTL:
            return

    try:
        cf = fetch_codeforces_schedule()
    except (ContestScheduleError, Exception) as e:
        logging.warning(f"contest_calendar: CF schedule fetch failed: {e}")
        cf = []

    try:
        lc = fetch_leetcode_schedule()
    except (ContestScheduleError, Exception) as e:
        logging.warning(f"contest_calendar: LC schedule fetch failed: {e}")
        lc = []

    with _lock:
        if not cf and not lc:
            # Both upstreams failed. Flag the cache as untrustworthy so the
            # gating predicate fails-open and we keep awarding points.
            _last_load_failed = True
            return

        _cache = cf + lc
        _cache_loaded_at = datetime.now(timezone.utc)
        _last_load_failed = False


def any_contest_between(t1: datetime, t2: datetime) -> bool:
    """
    True if any LC or CF contest's end_time + grace falls in (t1, t2].

    Used by the /submit gate: pass (user.last_contest_poll_at, now) to ask
    "could anything have happened since we last polled this user?"

    Fail-open: returns True when the global cache is empty due to upstream
    failure, so per-user polling proceeds and points are never missed.
    """
    if t2 <= t1:
        return False  # Defensive: empty window can't contain anything.

    _refresh_if_stale()
    if _last_load_failed or not _cache:
        return True  # Fail-open.

    for c in _cache:
        effective_end = c.end_time + _RATING_GRACE
        if t1 < effective_end <= t2:
            return True
    return False


def cache_state() -> dict:
    """Diagnostic helper for tests + debug commands. Not used in the hot path."""
    return {
        "size": len(_cache),
        "loaded_at": _cache_loaded_at.isoformat() if _cache_loaded_at else None,
        "last_load_failed": _last_load_failed,
    }


def _reset_cache_for_tests() -> None:
    """Used by the test suite to force a fresh refresh. Do not call in production."""
    global _cache, _cache_loaded_at, _last_load_failed
    with _lock:
        _cache = []
        _cache_loaded_at = None
        _last_load_failed = False
