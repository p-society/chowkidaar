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

from datetime import datetime, timezone
from typing import List, Optional

import requests

from integrations.contest_types import ContestEntry

CF_USER_RATING_URL = "https://codeforces.com/api/user.rating"


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
        CF rate-limits to 1 req/2 seconds per IP. The poller is responsible
        for spacing calls; this function does not sleep.
    """
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
