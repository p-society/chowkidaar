"""
Migration: add last_contest_poll_at to student_list_2024.

This timestamp lets /submit answer "did any LC or CF contest happen since
the last time I polled this user?" — if the answer is no, the handler skips
the expensive per-user API call entirely.

Idempotent: safe to run multiple times.

Run with:
    uv run --python 3.12 scripts/init_contest_gate.py
"""

import sys
import os

# Allow `import db.db` from this script.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: F401  (side effect: load env)
from db.db import connect_to_database


SCHEMA_STATEMENTS = [
    """
    ALTER TABLE student_list_2024
        ADD COLUMN IF NOT EXISTS last_contest_poll_at TIMESTAMPTZ;
    """,
]


def init_contest_gate() -> None:
    conn = connect_to_database()
    if not conn:
        print("Failed to connect to database")
        return
    try:
        cur = conn.cursor()
        for stmt in SCHEMA_STATEMENTS:
            cur.execute(stmt)
        conn.commit()
        print("✅ contest gate migration complete (last_contest_poll_at on student_list_2024).")
    except Exception as e:
        print("Migration error:", e)
        conn.rollback()
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    init_contest_gate()
