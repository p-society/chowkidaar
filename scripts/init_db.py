import sys
import os

# Add parent directory to path so we can import config/db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: F401
import psycopg2
from db.db import connect_to_database

SCHEMA_STATEMENTS = [
    # 1. Base Tables
    """
    CREATE TABLE IF NOT EXISTS student_list_2024 (
        stu_id VARCHAR(50) PRIMARY KEY,
        name VARCHAR(255),
        lc_handle VARCHAR(100),
        cf_handle VARCHAR(100),
        q1 TEXT[] DEFAULT '{}',
        q2 TEXT[] DEFAULT '{}',
        q3 TEXT[] DEFAULT '{}',
        all_solved TEXT[] DEFAULT '{}',
        is_late BOOLEAN DEFAULT FALSE,
        total_solved INTEGER DEFAULT 0
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS participation_logs (
        id SERIAL PRIMARY KEY,
        sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT NULL,
        deleted_at TIMESTAMP DEFAULT NULL,
        message TEXT,
        discord_user_id BIGINT,
        discord_message_id BIGINT,
        in_text_valid INT DEFAULT -1
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS day_brackets (
        day VARCHAR(10) PRIMARY KEY,
        initial_time TIMESTAMP,
        final_time TIMESTAMP
    );
    """,
    
    # 2. Migrations for student_list_2024
    """
    ALTER TABLE student_list_2024
        ADD COLUMN IF NOT EXISTS discord_user_id BIGINT,
        ADD COLUMN IF NOT EXISTS nickname_badge_enabled BOOLEAN NOT NULL DEFAULT TRUE,
        ADD COLUMN IF NOT EXISTS last_contest_poll_at TIMESTAMPTZ;
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_student_list_2024_discord_user_id
        ON student_list_2024 (discord_user_id);
    """,

    # 3. Badges System
    """
    CREATE TABLE IF NOT EXISTS badges (
        key             TEXT PRIMARY KEY,
        name            TEXT NOT NULL,
        description     TEXT,
        category        TEXT NOT NULL,
        discord_role_id BIGINT,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        emoji           TEXT,
        display_priority INTEGER NOT NULL DEFAULT 0
    );
    """,
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

    # 4. Contest Attendance
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

    # 5. Contest Reminders
    """
    CREATE TABLE IF NOT EXISTS contest_reminders_sent (
        contest_url    TEXT        NOT NULL,
        reminder_type  TEXT        NOT NULL,
        sent_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (contest_url, reminder_type)
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_contest_reminders_sent_at
        ON contest_reminders_sent (sent_at);
    """,
]

SEED_BADGES = [
    # (key, name, description, category, emoji, display_priority)
    ("day7_done",  "Day 7 Done",  "Submitted on at least 7 days of the event",  "milestone", "🥉", 10),
    ("day14_done", "Day 14 Done", "Submitted on at least 14 days of the event", "milestone", "🥈", 20),
    ("day25_done", "Day 25 Done", "Completed the full 25-day challenge",        "milestone", "🥇", 30),
    ("contest_participant", "Contest Participant", "Attended at least one LC or CF contest during the event", "contest", "🎯", 15),
    ("contest_rating_climber", "Rating Climber",   "Gained rating in at least one LC or CF contest",          "contest", "📈", 18),
]

def init_db():
    conn = connect_to_database()
    if not conn:
        print("Failed to connect to database")
        return
        
    try:
        cur = conn.cursor()
        
        # 1. Run all schema definitions
        for stmt in SCHEMA_STATEMENTS:
            cur.execute(stmt)
            
        # 2. Seed badge catalog
        cur.executemany(
            """
            INSERT INTO badges (key, name, description, category, emoji, display_priority)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (key) DO UPDATE SET
                emoji = EXCLUDED.emoji,
                display_priority = EXCLUDED.display_priority;
            """,
            SEED_BADGES,
        )

        conn.commit()
        print("✅ Database initialization and migrations complete!")

        # Print final state for sanity
        cur.execute("SELECT key, name, emoji, display_priority FROM badges ORDER BY display_priority DESC, key;")
        print("Badge catalog display order:")
        for key, name, emoji, prio in cur.fetchall():
            print(f"  prio={prio:>3}  {emoji or '∅':<4}  {key:<24} - {name}")
            
    except Exception as e:
        print("Error during database initialization:", e)
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    init_db()
