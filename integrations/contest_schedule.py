"""
Global contest schedules.

Backs db/contest_calendar.py — the /submit handler uses it to gate per-user
contest polls. If no LC or CF contest has happened recently, we skip the
expensive per-user API call entirely.

Public surface:
    fetch_codeforces_schedule() -> list[ContestSchedule]
    fetch_leetcode_schedule()   -> list[ContestSchedule]

Both raise ContestScheduleError on hard API failures so the caller can
fail-open (assume a contest did happen) rather than silently miss credit.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List

import requests

CF_CONTEST_LIST_URL = "https://codeforces.com/api/contest.list"
LC_GRAPHQL_URL = "https://leetcode.com/graphql"


@dataclass
class ContestSchedule:
    platform: str           # "leetcode" | "codeforces"
    contest_id: str
    contest_name: str
    start_time: datetime    # UTC, tz-aware
    duration_seconds: int

    @property
    def end_time(self) -> datetime:
        return self.start_time + timedelta(seconds=self.duration_seconds)


class ContestScheduleError(RuntimeError):
    """Raised when an upstream contest-list API returns an error payload."""


# ──────────────────────────────────────────────────────────────────────────
# Codeforces — public REST, no auth.
# Docs: https://codeforces.com/apiHelp/methods#contest.list
# ──────────────────────────────────────────────────────────────────────────

def fetch_codeforces_schedule(timeout: float = 10.0) -> List[ContestSchedule]:
    """Return every CF contest the API knows about that has a startTime.

    Includes BEFORE / CODING / FINISHED phases — we want all of them so the
    gate can detect both ongoing and recently-ended contests.
    """
    resp = requests.get(
        CF_CONTEST_LIST_URL,
        params={"gym": "false"},
        headers={"User-Agent": "chowkidaar-bot/1.0 (contest-gate)"},
        timeout=timeout,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("status") != "OK":
        raise ContestScheduleError(
            f"CF contest.list failed: {payload.get('comment', 'unknown error')}"
        )

    out: List[ContestSchedule] = []
    for c in payload.get("result", []):
        st = c.get("startTimeSeconds")
        dur = c.get("durationSeconds")
        if st is None or dur is None:
            # Some BEFORE-phase entries occasionally lack a startTime; skip.
            continue
        out.append(
            ContestSchedule(
                platform="codeforces",
                contest_id=str(c.get("id")),
                contest_name=c.get("name", ""),
                start_time=datetime.fromtimestamp(int(st), tz=timezone.utc),
                duration_seconds=int(dur),
            )
        )
    return out


# ──────────────────────────────────────────────────────────────────────────
# LeetCode — public GraphQL, no auth. Same endpoint and UA dance as the
# per-user history fetch. Pulls the full contest catalog at once.
# ──────────────────────────────────────────────────────────────────────────

LC_ALL_CONTESTS_QUERY = """
query allContestsForCalendar {
  allContests {
    title
    titleSlug
    startTime
    duration
  }
}
"""


def fetch_leetcode_schedule(timeout: float = 10.0) -> List[ContestSchedule]:
    """Return every LC contest (past + upcoming) with start_time + duration."""
    resp = requests.post(
        LC_GRAPHQL_URL,
        json={"query": LC_ALL_CONTESTS_QUERY},
        headers={
            "User-Agent": "Mozilla/5.0 (chowkidaar bot; contest-gate)",
            "Content-Type": "application/json",
            "Referer": "https://leetcode.com/contest/",
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    payload = resp.json()
    if "errors" in payload:
        raise ContestScheduleError(f"LC GraphQL error: {payload['errors']}")

    contests = ((payload.get("data") or {}).get("allContests")) or []
    out: List[ContestSchedule] = []
    for c in contests:
        st = c.get("startTime")
        dur = c.get("duration")
        if st is None or dur is None:
            continue
        out.append(
            ContestSchedule(
                platform="leetcode",
                contest_id=c.get("titleSlug") or c.get("title", ""),
                contest_name=c.get("title", ""),
                start_time=datetime.fromtimestamp(int(st), tz=timezone.utc),
                duration_seconds=int(dur),
            )
        )
    return out
