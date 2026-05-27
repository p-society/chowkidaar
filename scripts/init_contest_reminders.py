"""
Migration: add contest_reminders_sent table.

Used by cogs/contests.py to dedupe contest-start reminders across bot
restarts. Without this, restarting the bot during a reminder window would
re-fire the @CONTEST_ROLE ping for every contest still inside that window.

Idempotent: safe to run multiple times.

Run with:
    uv run --python 3.12 scripts/init_contest_reminders.py
"""

import sys
import os

# Allow `import db.db` from this script.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: F401  (side effect: load env)
from db.db import connect_to_database


SCHEMA_STATEMENTS = [
    # One row per (contest, reminder_kind). PRIMARY KEY does the dedup work;
    # we don't need a SERIAL id.
    """
    CREATE TABLE IF NOT EXISTS contest_reminders_sent (
        contest_url    TEXT        NOT NULL,
        reminder_type  TEXT        NOT NULL,  -- '12h' | '15m' | '0m'
        sent_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (contest_url, reminder_type)
    );
    """,
    # Cheap to add — lets cleanup queries (delete rows older than N days)
    # avoid a sequential scan once the table grows.
    """
    CREATE INDEX IF NOT EXISTS idx_contest_reminders_sent_at
        ON contest_reminders_sent (sent_at);
    """,
]


def init_contest_reminders() -> None:
    conn = connect_to_database()
    if not conn:
        print("Failed to connect to database")
        return
    try:
        cur = conn.cursor()
        for stmt in SCHEMA_STATEMENTS:
            cur.execute(stmt)
        conn.commit()
        print("✅ contest_reminders_sent table ready.")
    except Exception as e:
        print("Migration error:", e)
        conn.rollback()
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    init_contest_reminders()
