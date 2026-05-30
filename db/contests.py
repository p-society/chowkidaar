"""
Contest recording + points.

Pipeline:
  /submit handler  →  record_user_contests(discord_user_id)  →  LC + CF APIs
                                                              →  contest_attendance
                                                              →  award contest_* badges
                                                              →  returns (new ContestEntries, new badge metas)

Idempotency: enforced at the DB layer by UNIQUE(discord_user_id, platform,
contest_id) on contest_attendance. Re-running record_user_contests is safe.

Async-friendly: the underlying HTTP clients are blocking (requests), so we
wrap them in asyncio.to_thread so they don't stall the bot's event loop.

Public surface:
    record_user_contests(discord_user_id) -> tuple[list[ContestEntry], list[dict]]
        (newly-recorded contests, badge metadata dicts for any badges
        awarded this call). Either list may be empty.

    contest_points() -> int
        Per-contest reward points from configs/event_config.json.

    get_contest_points_total(discord_user_id) -> int
        Sum of points_awarded from contest_attendance for the user.

    get_contest_points_per_user() -> dict[int, int]
        For future /leaderboard. Returns {discord_user_id: total_points, ...}.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import List, Optional, Tuple

import psycopg2
from psycopg2 import errors

from db.db import connect_to_database, total_db_operations

_last_contest_poll_at_exists = None
from db.contest_calendar import any_contest_between
from integrations.contest_types import ContestEntry
from integrations.leetcode_contests import (
    LeetCodeAPIError,
    fetch_user_contests as _fetch_lc,
)
from integrations.codeforces_contests import (
    CodeforcesAPIError,
    fetch_user_contests as _fetch_cf,
)
from utils.event_window import _load_config, get_event_window


# ──────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────

def contest_points() -> int:
    """Read configs/event_config.json → points.contest_participation. Default 10."""
    cfg = _load_config()
    return int((cfg.get("points") or {}).get("contest_participation", 10))


# Back-compat alias for the original private name. New callers should use
# the public `contest_points()` instead.
_contest_points = contest_points


# ──────────────────────────────────────────────────────────────────────────
# Handle lookup
# ──────────────────────────────────────────────────────────────────────────

def _get_user_handles(discord_user_id: int) -> Tuple[Optional[str], Optional[str]]:
    """Return (lc_handle, cf_handle) for a Discord user, or (None, None) if not registered."""
    conn = connect_to_database(purpose="Fetch User Handles")
    if not conn:
        return (None, None)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT NULLIF(TRIM(lc_handle), ''), NULLIF(TRIM(cf_handle), '')
                FROM student_list_2024
                WHERE discord_user_id = %s
                LIMIT 1
                """,
                (discord_user_id,),
            )
            row = cur.fetchone()
            return (row[0], row[1]) if row else (None, None)
    except psycopg2.Error as e:
        logging.error(f"_get_user_handles error: {e}")
        return (None, None)
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────
# Per-user poll-throttling state
# ──────────────────────────────────────────────────────────────────────────

def _get_last_contest_poll_at(discord_user_id: int) -> Optional[datetime]:
    """
    Return the timestamp of this user's most recent contest poll, or None if
    they've never been polled (or if the migration hasn't been run yet).

    UndefinedColumn is treated as "no migration yet, return None" so the bot
    keeps working before scripts/init_contest_gate.py has been applied —
    the gate just degrades to "always poll" until then.
    """
    conn = connect_to_database(purpose="Fetch Last Contest Poll Timestamp")
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT last_contest_poll_at
                FROM student_list_2024
                WHERE discord_user_id = %s
                LIMIT 1
                """,
                (discord_user_id,),
            )
            row = cur.fetchone()
            return row[0] if row and row[0] else None
    except errors.UndefinedColumn:
        # Pre-migration — silently degrade.
        return None
    except psycopg2.Error as e:
        logging.error(f"_get_last_contest_poll_at error: {e}")
        return None
    finally:
        conn.close()


def _set_last_contest_poll_at(discord_user_id: int, when: datetime) -> None:
    """Stamp `last_contest_poll_at = when` for this user. Best-effort."""
    conn = connect_to_database(purpose="Update Last Contest Poll Timestamp")
    if not conn:
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE student_list_2024
                SET last_contest_poll_at = %s
                WHERE discord_user_id = %s
                """,
                (when, discord_user_id),
            )
            conn.commit()
            total_db_operations.inc()
    except errors.UndefinedColumn:
        # Pre-migration — quietly skip the write.
        conn.rollback()
    except psycopg2.Error as e:
        logging.error(f"_set_last_contest_poll_at error: {e}")
        conn.rollback()
    finally:
        conn.close()


# ──────────────────────────────────────────────────────────────────────────
# Public: record contests
# ──────────────────────────────────────────────────────────────────────────

def _record_contests_db_tx(
    discord_user_id: int,
    fetched: List[ContestEntry],
    points: int,
    start_utc: datetime,
    end_utc: datetime,
    now: datetime,
) -> Tuple[List[ContestEntry], List[dict]]:
    conn = connect_to_database(purpose="Record Contest Performance & Award Badges")
    if not conn:
        return ([], [])
    try:
        # 1. Fetch existing contests
        existing_contests = set()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT platform, contest_id
                FROM contest_attendance
                WHERE discord_user_id = %s
                """,
                (discord_user_id,),
            )
            for plat, cid in cur.fetchall():
                existing_contests.add((plat, cid))

        # 2. Insert newly fetched contests
        newly_recorded: List[ContestEntry] = []
        with conn.cursor() as cur:
            for entry in fetched:
                is_new = (entry.platform, entry.contest_id) not in existing_contests
                cur.execute(
                    """
                    INSERT INTO contest_attendance
                        (discord_user_id, platform, contest_id, contest_name,
                         contest_date, rank, rating_delta, points_awarded)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (discord_user_id, platform, contest_id) DO UPDATE
                    SET rank = COALESCE(contest_attendance.rank, EXCLUDED.rank),
                        rating_delta = COALESCE(contest_attendance.rating_delta, EXCLUDED.rating_delta)
                    """,
                    (
                        discord_user_id,
                        entry.platform,
                        entry.contest_id,
                        entry.contest_name,
                        entry.contest_date,
                        entry.rank,
                        entry.rating_delta,
                        points,
                    ),
                )
                if is_new:
                    newly_recorded.append(entry)

        # 3. Update last poll status timestamp if the column exists (cached in-memory)
        global _last_contest_poll_at_exists
        if _last_contest_poll_at_exists is None:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.columns 
                            WHERE table_name = 'student_list_2024' 
                              AND column_name = 'last_contest_poll_at'
                        );
                    """)
                    _last_contest_poll_at_exists = cur.fetchone()[0]
            except Exception:
                _last_contest_poll_at_exists = False

        if _last_contest_poll_at_exists:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE student_list_2024
                    SET last_contest_poll_at = %s
                    WHERE discord_user_id = %s
                    """,
                    (now, discord_user_id),
                )

        # 4. Fetch all contests in event window
        all_contests = []
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT rank, rating_delta
                FROM contest_attendance
                WHERE discord_user_id = %s
                  AND contest_date >= %s
                  AND contest_date < %s
                """,
                (discord_user_id, start_utc, end_utc),
            )
            all_contests = cur.fetchall()

        # 5. Award badges reusing our database connection
        awarded_badges: List[dict] = []
        from db.badges import award_badge

        badge_qualifiers = {
            "contest_participant": len(all_contests) > 0,
            "contest_rating_climber": any(
                (delta is not None and delta > 0) for _, delta in all_contests
            ),
        }

        for badge_key, qualifies in badge_qualifiers.items():
            if not qualifies:
                continue
            with conn.cursor() as sp_cur:
                sp_cur.execute("SAVEPOINT award_badge_sp;")
            try:
                meta = award_badge(discord_user_id, badge_key, conn=conn)
                if meta is not None:
                    awarded_badges.append(meta)
                with conn.cursor() as sp_cur:
                    sp_cur.execute("RELEASE SAVEPOINT award_badge_sp;")
            except Exception as e:
                with conn.cursor() as sp_cur:
                    sp_cur.execute("ROLLBACK TO SAVEPOINT award_badge_sp;")
                logging.error(f"{badge_key} award failed for {discord_user_id}: {e}")

        conn.commit()
        total_db_operations.inc()
        return (newly_recorded, awarded_badges)
    except psycopg2.Error as e:
        logging.error(f"contest db transaction failed for {discord_user_id}: {e}")
        conn.rollback()
        return ([], [])
    finally:
        conn.close()


async def record_user_contests(
    discord_user_id: int,
) -> Tuple[List[ContestEntry], List[dict]]:
    """
    Poll LC + CF for this user, INSERT new contest_attendance rows, evaluate
    contest-category badges, and return both:

        (newly_recorded_contests, newly_awarded_badge_metas)

    Behaviour:
      - If neither handle is set, returns ([], []) immediately (no API calls).
      - GATE: if we've polled this user before AND no LC/CF contest has
        ended (with grace) since then, we skip the per-user API calls
        entirely. The global contest calendar is consulted to make this
        decision; on calendar failure we fail-open and poll anyway.
      - If one platform errors, the other still proceeds (partial success).
      - Existing contest_attendance rows are skipped via ON CONFLICT DO NOTHING.
      - Always returns; never raises.

    Badges awarded here (all idempotent via UNIQUE on user_badges):
      - contest_participant:     any new contest recorded this call.
      - contest_rating_climber:  any newly-recorded contest with rating_delta > 0.
    """
    lc_handle, cf_handle = _get_user_handles(discord_user_id)
    if not lc_handle and not cf_handle:
        return ([], [])

    now = datetime.now(timezone.utc)

    # ── GATE: skip the per-user poll if nothing happened since last time ─
    # First-ever poll (last_poll is None) always runs so we backfill any
    # contests the user attended before they ever hit /submit.
    last_poll = await asyncio.to_thread(_get_last_contest_poll_at, discord_user_id)
    if last_poll is not None:
        has_new_contest = await asyncio.to_thread(any_contest_between, last_poll, now)
        if not has_new_contest:
            # Nothing to do — but DON'T advance the timestamp; we didn't
            # actually re-confirm there's no new attendance. Leaving it untouched
            # is safe because any_contest_between() will return False again next
            # time too, until the calendar surfaces a new contest.
            return ([], [])

    start_utc, end_utc = get_event_window()
    points = contest_points()

    # ── Fan-out the two HTTP fetches in parallel via threads ────────────
    async def safe_lc() -> List[ContestEntry]:
        if not lc_handle:
            return []
        try:
            return await asyncio.to_thread(
                _fetch_lc, lc_handle,
                since=start_utc, until=end_utc, only_attended=True,
            )
        except LeetCodeAPIError as e:
            logging.warning(f"LC fetch: no data for @{lc_handle}: {e}")
        except Exception as e:
            logging.error(f"LC fetch failed for @{lc_handle}: {e}")
        return []

    async def safe_cf() -> List[ContestEntry]:
        if not cf_handle:
            return []
        try:
            return await asyncio.to_thread(
                _fetch_cf, cf_handle, since=start_utc, until=end_utc,
            )
        except CodeforcesAPIError as e:
            logging.warning(f"CF fetch: API failed for @{cf_handle}: {e}")
        except Exception as e:
            logging.error(f"CF fetch failed for @{cf_handle}: {e}")
        return []

    lc_results, cf_results = await asyncio.gather(safe_lc(), safe_cf())
    fetched: List[ContestEntry] = [*lc_results, *cf_results]
    if not fetched:
        # We did call the upstream APIs and got nothing — stamp last_poll so
        # the gate can short-circuit subsequent /submits until a new contest
        # actually happens.
        await asyncio.to_thread(_set_last_contest_poll_at, discord_user_id, now)
        return ([], [])

    # Consolidate all database actions into a single synchronous transaction thread
    return await asyncio.to_thread(
        _record_contests_db_tx,
        discord_user_id, fetched, points, start_utc, end_utc, now
    )


# ──────────────────────────────────────────────────────────────────────────
# Public: totals (used by /card and future /leaderboard)
# ──────────────────────────────────────────────────────────────────────────

def get_contest_points_total(discord_user_id: int) -> int:
    """Sum of points_awarded across this user's contest_attendance rows."""
    conn = connect_to_database(purpose="Fetch Total Contest Points")
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(points_awarded), 0)
                FROM contest_attendance
                WHERE discord_user_id = %s
                """,
                (discord_user_id,),
            )
            (total,) = cur.fetchone()
            return int(total or 0)
    except psycopg2.Error as e:
        logging.error(f"get_contest_points_total error: {e}")
        return 0
    finally:
        conn.close()


def get_contest_points_per_user() -> dict[int, int]:
    """{discord_user_id: total_contest_points} for the whole cohort. For leaderboards."""
    conn = connect_to_database(purpose="Fetch Contest Points Leaderboard")
    if not conn:
        return {}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT discord_user_id, COALESCE(SUM(points_awarded), 0)
                FROM contest_attendance
                GROUP BY discord_user_id
                """
            )
            return {row[0]: int(row[1] or 0) for row in cur.fetchall()}
    except psycopg2.Error as e:
        logging.error(f"get_contest_points_per_user error: {e}")
        return {}
    finally:
        conn.close()
