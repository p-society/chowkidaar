"""
Migration: add badge and contest-attendance tables, plus a discord_user_id
column on student_list_2024 so we can join everything to participation_logs.

Idempotent: safe to run multiple times.

Run with:
    uv run --python 3.12 scripts/init_badges_contests.py
"""

import sys
import os

# Allow `import db.db` from this script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: F401  (side effect: load env)
from db.db import connect_to_database


SCHEMA_STATEMENTS = [
    # 1) Link student records to Discord user IDs so we can join participation
    #    logs / contests / badges on a single key.
    """
    ALTER TABLE student_list_2024
        ADD COLUMN IF NOT EXISTS discord_user_id BIGINT;
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_student_list_2024_discord_user_id
        ON student_list_2024 (discord_user_id);
    """,

    # 2) Catalog of all possible badges.
    """
    CREATE TABLE IF NOT EXISTS badges (
        key             TEXT PRIMARY KEY,
        name            TEXT NOT NULL,
        description     TEXT,
        category        TEXT NOT NULL,        -- 'milestone' | 'contest'
        discord_role_id BIGINT,               -- set later, when role is created in Discord
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """,

    # 3) Which badges each user has earned.
    """
    CREATE TABLE IF NOT EXISTS user_badges (
        discord_user_id BIGINT      NOT NULL,
        badge_key       TEXT        NOT NULL REFERENCES badges(key) ON DELETE CASCADE,
        awarded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (discord_user_id, badge_key)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_user_badges_user
        ON user_badges (discord_user_id);
    """,

    # 4) Contest attendance + awarded points. UNIQUE makes the poller idempotent.
    """
    CREATE TABLE IF NOT EXISTS contest_attendance (
        id               SERIAL PRIMARY KEY,
        discord_user_id  BIGINT      NOT NULL,
        platform         TEXT        NOT NULL CHECK (platform IN ('leetcode','codeforces')),
        contest_id       TEXT        NOT NULL,
        contest_name     TEXT,
        contest_date     TIMESTAMPTZ NOT NULL,
        rank             INTEGER,
        rating_delta     INTEGER,
        points_awarded   INTEGER     NOT NULL DEFAULT 10,
        recorded_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE (discord_user_id, platform, contest_id)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_contest_attendance_user
        ON contest_attendance (discord_user_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_contest_attendance_date
        ON contest_attendance (contest_date);
    """,
]


# Seed the initial badge catalog. discord_role_id is left NULL — fill it in
# once the matching roles exist in your Discord server.
SEED_BADGES = [
    # milestone
    ("day7_done",  "Day 7 Done",  "Submitted on at least 7 days of the event",  "milestone"),
    ("day14_done", "Day 14 Done", "Submitted on at least 14 days of the event", "milestone"),
    ("day25_done", "Day 25 Done", "Completed the full 25-day challenge",        "milestone"),
    # contest
    ("contest_participant", "Contest Participant", "Attended at least one LC or CF contest during the event", "contest"),
    ("contest_top_100",     "Top 100",             "Finished in the top 100 of any LC or CF contest",         "contest"),
    ("contest_rating_climber", "Rating Climber",   "Gained rating in at least one LC or CF contest",          "contest"),
]


def init_badges_contests():
    conn = connect_to_database()
    if not conn:
        print("Failed to connect to database")
        return

    try:
        cur = conn.cursor()

        for stmt in SCHEMA_STATEMENTS:
            cur.execute(stmt)

        # Seed badge catalog (idempotent via ON CONFLICT).
        cur.executemany(
            """
            INSERT INTO badges (key, name, description, category)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (key) DO NOTHING;
            """,
            SEED_BADGES,
        )

        conn.commit()

        # Print final state for sanity.
        cur.execute("SELECT key, name, category FROM badges ORDER BY category, key;")
        rows = cur.fetchall()
        print("Migration complete. Badge catalog:")
        for key, name, category in rows:
            print(f"  [{category:9}] {key:24} - {name}")

    except Exception as e:
        print("Migration error:", e)
        conn.rollback()
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    init_badges_contests()
