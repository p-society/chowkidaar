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


def list_user_badges(discord_user_id: int, conn=None) -> List[dict]:
    """Return all badges (with metadata + awarded_at) for one user."""
    should_close = False
    if not conn:
        conn = connect_to_database()
        should_close = True
    if not conn:
        return []
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT b.key, b.name, b.description, b.category,
                       b.discord_role_id, b.emoji, b.display_priority, ub.awarded_at
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
        if should_close:
            conn.close()


def has_badge(discord_user_id: int, badge_key: str, conn=None) -> bool:
    should_close = False
    if not conn:
        conn = connect_to_database()
        should_close = True
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
        if should_close:
            conn.close()


def award_badge(discord_user_id: int, badge_key: str, conn=None) -> Optional[dict]:
    """
    Award the badge to the user. Idempotent — if they already have it,
    returns None. Otherwise returns the badge metadata dict.
    """
    should_close = False
    if not conn:
        conn = connect_to_database()
        should_close = True
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
            if should_close:
                conn.commit()
            total_db_operations.inc()
            if not inserted:
                return None
            return _fetch_badge_meta(cur, badge_key)
    except psycopg2.Error as e:
        print(f"award_badge error: {e}")
        if should_close:
            conn.rollback()
        return None
    finally:
        if should_close:
            conn.close()


def count_distinct_submission_days(
    discord_user_id: int,
    start_utc: datetime,
    end_utc: datetime,
    conn=None,
) -> int:
    """
    Count the number of distinct calendar days (UTC) on which this user has
    a valid, non-deleted submission inside [start_utc, end_utc).
    """
    should_close = False
    if not conn:
        conn = connect_to_database()
        should_close = True
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(DISTINCT DATE((sent_at AT TIME ZONE 'UTC') - INTERVAL '16 hours 30 minutes'))
                FROM participation_logs
                WHERE discord_user_id = %s
                  AND deleted_at IS NULL
                  AND in_text_valid = 1
                  AND sent_at >= %s
                  AND sent_at <  %s + INTERVAL '1 day'
                """,
                (discord_user_id, start_utc, end_utc),
            )
            (count,) = cur.fetchone()
            return int(count or 0)
    except psycopg2.Error as e:
        print(f"count_distinct_submission_days error: {e}")
        return 0
    finally:
        if should_close:
            conn.close()


def get_top_badge_emoji(discord_user_id: int, conn=None) -> Optional[str]:
    """
    Return the emoji of the highest-priority badge this user has earned,
    or None if they have no badges (or none of their badges have an emoji set).
    """
    should_close = False
    if not conn:
        conn = connect_to_database()
        should_close = True
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
        if should_close:
            conn.close()
def format_name_with_badge(discord_user_id: int, name: str) -> str:
    return name


def get_all_badge_emojis(conn=None) -> List[str]:
    """Return every distinct emoji currently configured in the badges table.

    Used by the nickname helper to know what prefixes to strip.
    """
    should_close = False
    if not conn:
        conn = connect_to_database()
        should_close = True
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
        if should_close:
            conn.close()


def current_streak(discord_user_id: int, conn=None) -> int:
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
    should_close = False
    if not conn:
        conn = connect_to_database()
        should_close = True
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            # Pull every distinct UTC date the user has submitted, descending.
            # Bounded to the event window to keep this cheap.
            start_utc, end_utc = get_event_window()
            cur.execute(
                """
                SELECT DISTINCT DATE((sent_at AT TIME ZONE 'UTC') - INTERVAL '16 hours 30 minutes') AS d
                FROM participation_logs
                WHERE discord_user_id = %s
                  AND deleted_at IS NULL
                  AND in_text_valid = 1
                  AND sent_at >= %s
                  AND sent_at <  %s + INTERVAL '1 day'
                ORDER BY d DESC
                """,
                (discord_user_id, start_utc, end_utc),
            )
            dates = [row[0] for row in cur.fetchall()]
    except psycopg2.Error as e:
        print(f"current_streak error: {e}")
        return 0
    finally:
        if should_close:
            conn.close()

    if not dates:
        return 0

    from datetime import datetime, timezone, timedelta
    now_shifted = datetime.now(timezone.utc) - timedelta(hours=16, minutes=30)
    today = now_shifted.date()
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


def max_streak(discord_user_id: int, conn=None) -> int:
    """
    Longest consecutive-day run of valid submissions for this user inside the
    event window (UTC days). "Consecutive" means each day immediately follows
    the previous one — a one-day gap breaks the streak.

    Unlike current_streak (which only looks at the run anchored to today),
    this returns the user's best run *anywhere* in the event. Used to award
    streak-based milestone badges that, once earned, are kept forever even
    if the user later breaks their streak.
    """
    should_close = False
    if not conn:
        conn = connect_to_database()
        should_close = True
    if not conn:
        return 0
    try:
        with conn.cursor() as cur:
            start_utc, end_utc = get_event_window()
            cur.execute(
                """
                SELECT DISTINCT DATE((sent_at AT TIME ZONE 'UTC') - INTERVAL '16 hours 30 minutes') AS d
                FROM participation_logs
                WHERE discord_user_id = %s
                  AND deleted_at IS NULL
                  AND in_text_valid = 1
                  AND sent_at >= %s
                  AND sent_at <  %s + INTERVAL '1 day'
                ORDER BY d ASC
                """,
                (discord_user_id, start_utc, end_utc),
            )
            dates = [row[0] for row in cur.fetchall()]
    except psycopg2.Error as e:
        print(f"max_streak error: {e}")
        return 0
    finally:
        if should_close:
            conn.close()

    if not dates:
        return 0

    from datetime import timedelta
    best = 1
    run = 1
    for i in range(1, len(dates)):
        if dates[i] == dates[i - 1] + timedelta(days=1):
            run += 1
            if run > best:
                best = run
        else:
            run = 1
    return best


def check_and_award_milestones(discord_user_id: int, conn=None) -> List[dict]:
    """
    Award any milestone badges the user has just earned. Returns metadata for
    each newly awarded badge (so the caller can announce them in Discord).
    Already-held badges are silently skipped.

    Awarding is **streak-based**: a 7-day consecutive run earns `day7_done`,
    14-day earns `day14_done`, 25-day earns `day25_done`. Uses max_streak so
    that once earned, a badge sticks even if the user later breaks their run.
    """
    should_close = False
    if not conn:
        conn = connect_to_database()
        should_close = True
    if not conn:
        return []

    try:
        days = max_streak(discord_user_id, conn=conn)

        newly_awarded: List[dict] = []
        for threshold, badge_key in MILESTONE_THRESHOLDS:
            if days < threshold:
                continue
            meta = award_badge(discord_user_id, badge_key, conn=conn)
            if meta is not None:
                newly_awarded.append(meta)
        if should_close:
            conn.commit()
        return newly_awarded
    except Exception as e:
        if should_close:
            conn.rollback()
        raise e
    finally:
        if should_close:
            conn.close()
