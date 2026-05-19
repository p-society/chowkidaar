"""
Badge logic.

Pure DB layer: no Discord imports. The Discord-side effects (assigning a role,
posting a celebration embed) live in main.py and consume the metadata
returned by `check_and_award_milestones`.

Public surface:

    list_user_badges(discord_user_id) -> list[dict]
    has_badge(discord_user_id, badge_key) -> bool
    award_badge(discord_user_id, badge_key) -> dict | None
        # returns the badge metadata if newly awarded, None if already had it

    count_distinct_submission_days(discord_user_id, start_utc, end_utc) -> int

    check_and_award_milestones(discord_user_id) -> list[dict]
        # convenience: looks at participation_logs against the current event
        # window from utils.event_window, awards any newly-crossed milestone
        # badges, and returns metadata for each newly awarded badge.

Each "badge metadata" dict has keys:
    key, name, description, category, discord_role_id
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor

from db.db import connect_to_database, total_db_operations
from utils.event_window import get_event_window


from db.badges_config import get_milestone_thresholds

# Milestone thresholds dynamically loaded from centralized badges configuration
MILESTONE_THRESHOLDS = get_milestone_thresholds()


def _fetch_badge_meta(cur, badge_key: str) -> Optional[dict]:
    cur.execute(
        """
        SELECT key, name, description, category, discord_role_id
        FROM badges
        WHERE key = %s
        """,
        (badge_key,),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def list_user_badges(discord_user_id: int) -> List[dict]:
    """Return all badges (with metadata + awarded_at) for one user."""
    conn = connect_to_database()
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT b.key, b.name, b.description, b.category,
                       b.discord_role_id, b.emoji, ub.awarded_at
                FROM user_badges ub
                JOIN badges b ON b.key = ub.badge_key
                WHERE ub.discord_user_id = %s
                ORDER BY ub.awarded_at ASC
                """,
                (discord_user_id,),
            )
            return [dict(r) for r in cur.fetchall()]
    except psycopg2.Error as e:
        print(f"list_user_badges error: {e}")
        return []
    finally:
        conn.close()


def has_badge(discord_user_id: int, badge_key: str) -> bool:
    conn = connect_to_database()
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM user_badges WHERE discord_user_id = %s AND badge_key = %s",
                (discord_user_id, badge_key),
            )
            return cur.fetchone() is not None
    except psycopg2.Error as e:
        print(f"has_badge error: {e}")
        return False
    finally:
        conn.close()


def award_badge(discord_user_id: int, badge_key: str) -> Optional[dict]:
    """
    Award the badge to the user. Idempotent — if they already have it,
    returns None. Otherwise returns the badge metadata dict.
    """
    conn = connect_to_database()
    if not conn:
        return None
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO user_badges (discord_user_id, badge_key)
                VALUES (%s, %s)
                ON CONFLICT (discord_user_id, badge_key) DO NOTHING
                RETURNING discord_user_id
                """,
                (discord_user_id, badge_key),
            )
            inserted = cur.fetchone() is not None
            conn.commit()
            total_db_operations.inc()
            if not inserted:
                return None
            return _fetch_badge_meta(cur, badge_key)
    except psycopg2.Error as e:
        print(f"award_badge error: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


def count_distinct_submission_days(
    discord_user_id: int,
    start_utc: datetime,
    end_utc: datetime,
) -> int:
    """
    Count the number of distinct calendar days (UTC) on which this user has
    a valid, non-deleted submission inside [start_utc, end_utc).
    """
    conn = connect_to_database()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(DISTINCT DATE(sent_at AT TIME ZONE 'UTC'))
                FROM participation_logs
                WHERE discord_user_id = %s
                  AND deleted_at IS NULL
                  AND in_text_valid = 1
                  AND sent_at >= %s
                  AND sent_at <  %s
                """,
                (discord_user_id, start_utc, end_utc),
            )
            (count,) = cur.fetchone()
            return int(count or 0)
    except psycopg2.Error as e:
        print(f"count_distinct_submission_days error: {e}")
        return 0
    finally:
        conn.close()


def get_top_badge_emoji(discord_user_id: int) -> Optional[str]:
    """
    Return the emoji of the highest-priority badge this user has earned,
    or None if they have no badges (or none of their badges have an emoji set).
    """
    conn = connect_to_database()
    if not conn:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT b.emoji
                FROM user_badges ub
                JOIN badges b ON b.key = ub.badge_key
                WHERE ub.discord_user_id = %s
                  AND b.emoji IS NOT NULL
                ORDER BY b.display_priority DESC
                LIMIT 1
                """,
                (discord_user_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None
    except psycopg2.Error as e:
        print(f"get_top_badge_emoji error: {e}")
        return None
    finally:
        conn.close()
def format_name_with_badge(discord_user_id: int, name: str) -> str:
    return name


def get_all_badge_emojis() -> List[str]:
    """Return every distinct emoji currently configured in the badges table.

    Used by the nickname helper to know what prefixes to strip.
    """
    conn = connect_to_database()
    if not conn:
        return []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT emoji FROM badges WHERE emoji IS NOT NULL;")
            return [r[0] for r in cur.fetchall()]
    except psycopg2.Error as e:
        print(f"get_all_badge_emojis error: {e}")
        return []
    finally:
        conn.close()


def current_streak(discord_user_id: int) -> int:
    """
    Count the user's current consecutive-day submission streak, anchored to
    today (UTC). Walks backwards from today through participation_logs:

      - If they submitted today, today counts as day 1 of the streak.
      - If not, we start counting from yesterday — missing today doesn't
        immediately reset (they still have the rest of today to submit).
      - The streak breaks the first day with no valid submission.

    The walk is bounded to the event window so a streak doesn't accidentally
    extend before the event started.
    """
    conn = connect_to_database()
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            # Pull every distinct UTC date the user has submitted, descending.
            # Bounded to the event window to keep this cheap.
            start_utc, end_utc = get_event_window()
            cur.execute(
                """
                SELECT DISTINCT DATE(sent_at AT TIME ZONE 'UTC') AS d
                FROM participation_logs
                WHERE discord_user_id = %s
                  AND deleted_at IS NULL
                  AND in_text_valid = 1
                  AND sent_at >= %s
                  AND sent_at <  %s
                ORDER BY d DESC
                """,
                (discord_user_id, start_utc, end_utc),
            )
            dates = [row[0] for row in cur.fetchall()]
    except psycopg2.Error as e:
        print(f"current_streak error: {e}")
        return 0
    finally:
        conn.close()

    if not dates:
        return 0

    from datetime import date, timedelta
    today = date.today()
    # If today isn't in the set, allow yesterday as the anchor so missing today
    # doesn't pre-emptively break the streak.
    cursor = today if today in dates else today - timedelta(days=1)

    streak = 0
    for d in dates:
        if d == cursor:
            streak += 1
            cursor -= timedelta(days=1)
        elif d < cursor:
            # Gap detected — streak breaks here.
            break
        # d > cursor (future date somehow) shouldn't happen; ignore.
    return streak


def check_and_award_milestones(discord_user_id: int) -> List[dict]:
    """
    Award any milestone badges the user has just earned. Returns metadata for
    each newly awarded badge (so the caller can announce them in Discord).
    Already-held badges are silently skipped.
    """
    start_utc, end_utc = get_event_window()
    days = count_distinct_submission_days(discord_user_id, start_utc, end_utc)

    newly_awarded: List[dict] = []
    for threshold, badge_key in MILESTONE_THRESHOLDS:
        if days < threshold:
            continue
        meta = award_badge(discord_user_id, badge_key)
        if meta is not None:
            newly_awarded.append(meta)
    return newly_awarded
