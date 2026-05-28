"""
Codeforces contest history via the public REST API.

Endpoint: https://codeforces.com/api/user.rating?handle=<handle>
Docs:     https://codeforces.com/apiHelp/methods#user.rating

Returns rating changes per rated contest. Unrated participations are not
included here — Codeforces only emits an entry once a contest has been rated.

Public surface:
    fetch_user_contests(handle) -> list[ContestEntry]
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import List, Optional

import requests

from integrations.contest_types import ContestEntry

CF_USER_RATING_URL = "https://codeforces.com/api/user.rating"

# Codeforces enforces 1 request every 2 seconds per IP. We respect that here
# with a process-wide guard so concurrent /submit handlers can't accidentally
# burst and get rate-limited. The lock + monotonic timestamp pattern is
# thread-safe and friendly to asyncio.to_thread callers.
_CF_RATE_LOCK = threading.Lock()
_CF_LAST_CALL_AT: float = 0.0
_CF_MIN_INTERVAL_SEC: float = 2.0


def _wait_for_rate_limit() -> None:
    """Sleep just long enough to ensure ≥_CF_MIN_INTERVAL_SEC between calls."""
    global _CF_LAST_CALL_AT
    with _CF_RATE_LOCK:
        now = time.monotonic()
        wait = _CF_LAST_CALL_AT + _CF_MIN_INTERVAL_SEC - now
        if wait > 0:
            time.sleep(wait)
        _CF_LAST_CALL_AT = time.monotonic()


class CodeforcesAPIError(RuntimeError):
    """Raised when the CF API returns status != OK."""


def fetch_user_contests(
    handle: str,
    *,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    timeout: float = 10.0,
) -> List[ContestEntry]:
    """
    Return the user's Codeforces (rated) contest history.

    Args:
        handle: Codeforces handle.
        since / until: optional UTC datetimes for filtering.
        timeout: per-request timeout in seconds.

    Raises:
        CodeforcesAPIError: if the API returns a FAILED status (e.g. handle
            not found).
        requests.RequestException: on network failures.

    Note:
        CF rate-limits to 1 req/2 seconds per IP. This function blocks on a
        process-wide lock to enforce that, so concurrent callers are safe.
    """
    _wait_for_rate_limit()
    resp = requests.get(
        CF_USER_RATING_URL,
        params={"handle": handle},
        headers={"User-Agent": "chowkidaar-bot/1.0"},
        timeout=timeout,
    )
    resp.raise_for_status()
    payload = resp.json()

    if payload.get("status") != "OK":
        raise CodeforcesAPIError(
            f"CF API failed for handle {handle!r}: {payload.get('comment', 'unknown error')}"
        )

    entries: List[ContestEntry] = []
    for row in payload.get("result", []):
        ts = row.get("ratingUpdateTimeSeconds")
        if ts is None:
            continue

        contest_date = datetime.fromtimestamp(int(ts), tz=timezone.utc)
        if since is not None and contest_date < since:
            continue
        if until is not None and contest_date > until:
            continue

        old_rating = row.get("oldRating")
        new_rating = row.get("newRating")
        delta = (new_rating - old_rating) if (old_rating is not None and new_rating is not None) else None

        entries.append(
            ContestEntry(
                platform="codeforces",
                contest_id=str(row.get("contestId")),
                contest_name=row.get("contestName", ""),
                contest_date=contest_date,
                rank=row.get("rank"),
                rating_delta=delta,
                attended=True,  # CF only returns rated participations, so always True
            )
        )

    entries.sort(key=lambda e: e.contest_date)
    return entries
