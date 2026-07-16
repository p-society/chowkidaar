"""
LeetCode contest history via the public GraphQL endpoint.

The endpoint is unofficial but stable and widely used. We query
`userContestRankingHistory`, which returns every contest the user has
registered for, with attendance, rank, and rating data.

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

LEETCODE_GRAPHQL_URL = "https://leetcode.com/graphql"

# LeetCode's GraphQL endpoint is unofficial and has no documented rate limit,
# but we don't want to get our IP shadow-banned. One request per second is
# polite and well below anything they'd flag. Same thread-safe pattern as the
# Codeforces client.
_LC_RATE_LOCK = threading.Lock()
_LC_LAST_CALL_AT: float = 0.0
_LC_MIN_INTERVAL_SEC: float = 1.0


def _wait_for_rate_limit() -> None:
    global _LC_LAST_CALL_AT
    with _LC_RATE_LOCK:
        now = time.monotonic()
        wait = _LC_LAST_CALL_AT + _LC_MIN_INTERVAL_SEC - now
        if wait > 0:
            time.sleep(wait)
        _LC_LAST_CALL_AT = time.monotonic()

# Query both summary stats and full history. We only use the history in
# fetch_user_contests, but keeping the summary makes it easy to surface
# "attended N contests, current rating R" in /stats later.
QUERY = """
query userContestRankingInfo($username: String!) {
  userContestRanking(username: $username) {
    attendedContestsCount
    rating
    globalRanking
    totalParticipants
    topPercentage
  }
  userContestRankingHistory(username: $username) {
    attended
    trendDirection
    problemsSolved
    totalProblems
    finishTimeInSeconds
    rating
    ranking
    contest {
      title
      titleSlug
      startTime
    }
  }
}
"""


class LeetCodeAPIError(RuntimeError):
    """Raised when the GraphQL endpoint returns an error or no user."""


def _post(username: str, timeout: float = 10.0) -> dict:
    _wait_for_rate_limit()
    resp = requests.post(
        LEETCODE_GRAPHQL_URL,
        json={"query": QUERY, "variables": {"username": username}},
        headers={
            # LeetCode sits behind Cloudflare and will 403 / serve a challenge
            # page to user agents that look like bots (anything containing
            # "bot", custom client strings, etc.). Use a plain browser UA — the
            # same one db/platforms/leetcode.py uses successfully for profiles.
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Content-Type": "application/json",
            "Referer": f"https://leetcode.com/u/{username}/",
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    # When Cloudflare blocks the request it returns an HTML challenge page, not
    # JSON. Surface that as a clear error instead of letting json() blow up with
    # an opaque JSONDecodeError that callers silently swallow as "no contests".
    try:
        payload = resp.json()
    except ValueError as e:
        snippet = (resp.text or "")[:200].replace("\n", " ")
        raise LeetCodeAPIError(
            f"Non-JSON response for {username!r} (HTTP {resp.status_code}); "
            f"likely blocked by LeetCode/Cloudflare. Body starts: {snippet!r}"
        ) from e
    if "errors" in payload:
        raise LeetCodeAPIError(f"GraphQL error for {username!r}: {payload['errors']}")
    return payload.get("data") or {}


def fetch_user_contests(
    handle: str,
    *,
    since: Optional[datetime] = None,
    until: Optional[datetime] = None,
    only_attended: bool = True,
    timeout: float = 10.0,
) -> List[ContestEntry]:
    """
    Return the user's LeetCode contest history.

    Args:
        handle: LeetCode username.
        since / until: optional UTC datetimes; only contests with
            start_time in [since, until] are returned.
        only_attended: if True (default), skip contests the user
            registered for but didn't actually participate in.
        timeout: per-request timeout in seconds.

    Raises:
        LeetCodeAPIError: if the user doesn't exist or GraphQL errored.
        requests.RequestException: on network failures.
    """
    data = _post(handle, timeout=timeout)
    history = data.get("userContestRankingHistory")
    if history is None:
        raise LeetCodeAPIError(f"No contest data for handle {handle!r} (user may not exist)")

    # Filter and sort the entire raw history chronologically by start time to compute rating deltas
    valid_history = []
    for row in history:
        if row.get("contest") and row["contest"].get("startTime"):
            valid_history.append(row)
    valid_history.sort(key=lambda r: int(r["contest"]["startTime"]))

    entries: List[ContestEntry] = []
    prev_rating = 1500.0
    for row in valid_history:
        curr_rating = row.get("rating")
        
        # Calculate delta if rating is valid, and update previous rating tracker
        if curr_rating is not None and curr_rating > 0:
            delta = round(curr_rating - prev_rating)
            prev_rating = curr_rating
        else:
            delta = None
            
        if only_attended and not row.get("attended"):
            continue

        contest = row["contest"]
        start_ts = contest["startTime"]
        contest_date = datetime.fromtimestamp(int(start_ts), tz=timezone.utc)

        if since is not None and contest_date < since:
            continue
        if until is not None and contest_date > until:
            continue

        entries.append(
            ContestEntry(
                platform="leetcode",
                contest_id=contest.get("titleSlug") or contest.get("title", ""),
                contest_name=contest.get("title", ""),
                contest_date=contest_date,
                rank=row.get("ranking") or None,
                rating_delta=delta,
                attended=bool(row.get("attended")),
            )
        )

    # Return entries sorted chronologically
    entries.sort(key=lambda e: e.contest_date)
    return entries

