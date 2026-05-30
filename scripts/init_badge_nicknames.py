"""
Migration: add emoji + display_priority to badges, and nickname_badge_enabled
to student_list_2024. Seed emoji + priority for the existing six badges.

Idempotent: safe to run multiple times.

Run with:
    uv run --python 3.12 scripts/init_badge_nicknames.py
"""

import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: F401
from db.db import connect_to_database


SCHEMA = [
    """
    ALTER TABLE badges
        ADD COLUMN IF NOT EXISTS emoji TEXT,
        ADD COLUMN IF NOT EXISTS display_priority INTEGER NOT NULL DEFAULT 0;
    """,
    """
    ALTER TABLE student_list_2024
        ADD COLUMN IF NOT EXISTS nickname_badge_enabled BOOLEAN NOT NULL DEFAULT TRUE;
    """,
]

# (key, emoji, display_priority). Higher priority wins when a user has multiple
# badges — Day 25 should beat Day 14, Day 14 should beat Day 7, etc.
BADGE_DISPLAY = [
    ("day7_done",              "🥉", 10),
    ("day14_done",             "🥈", 20),
    ("day25_done",             "🥇", 30),
    ("contest_participant",    "🎯", 15),
    ("contest_rating_climber", "📈", 18),
]


def init():
    conn = connect_to_database()
    if not conn:
        print("Failed to connect"); return

    try:
        cur = conn.cursor()
        for stmt in SCHEMA:
            cur.execute(stmt)

        # Seed/update emoji + priority. Idempotent UPSERT-style update.
        cur.executemany(
            """
            UPDATE badges
               SET emoji = %s,
                   display_priority = %s
             WHERE key = %s
               AND (emoji IS DISTINCT FROM %s OR display_priority IS DISTINCT FROM %s)
            """,
            [(emoji, prio, key, emoji, prio) for (key, emoji, prio) in BADGE_DISPLAY],
        )

        conn.commit()

        cur.execute("SELECT key, name, emoji, display_priority FROM badges ORDER BY display_priority DESC, key;")
        print("Migration complete. Badge display order (highest priority first):")
        for key, name, emoji, prio in cur.fetchall():
            print(f"  prio={prio:>3}  {emoji or '∅':<4}  {key:<24} - {name}")
    except Exception as e:
        print("Migration error:", e)
        conn.rollback()
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    init()
