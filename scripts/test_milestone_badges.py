"""
End-to-end test for the milestone-badges hook against the real DB.

What it does:
  1. Picks a fake discord_user_id (default: 999999999999999999).
  2. Inserts 7 fake participation_logs rows on 7 distinct days inside the
     current event window.
  3. Calls check_and_award_milestones — expects 'day7_done' to be awarded.
  4. Calls again — expects no new awards (idempotency).
  5. Inserts 7 more rows on 7 more distinct days (total 14).
  6. Calls check_and_award_milestones — expects 'day14_done'.
  7. Optionally cleans up.

Usage:
    uv run --python 3.12 scripts/test_milestone_badges.py          # run + cleanup
    uv run --python 3.12 scripts/test_milestone_badges.py --keep   # leave rows in DB
"""

import sys
import os
from datetime import timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: F401
from db.db import connect_to_database
from db.badges import (
    check_and_award_milestones,
    list_user_badges,
    count_distinct_submission_days,
)
from utils.event_window import get_event_window


FAKE_USER_ID = 999999999999999999  # 18 digits — fits BIGINT, unlikely to collide


def _insert_fake_logs(conn, days_offsets):
    """Insert one valid log for each day offset from event start."""
    start_utc, _ = get_event_window()
    with conn.cursor() as cur:
        for offset in days_offsets:
            ts = start_utc + timedelta(days=offset, hours=12)
            cur.execute(
                """
                INSERT INTO participation_logs
                    (message, discord_user_id, discord_message_id, sent_at, in_text_valid)
                VALUES (%s, %s, %s, %s, 1)
                """,
                (f"fake test log day{offset}", FAKE_USER_ID, ts.timestamp(), ts),
            )
    conn.commit()


def _cleanup(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM user_badges WHERE discord_user_id = %s", (FAKE_USER_ID,))
        cur.execute("DELETE FROM participation_logs WHERE discord_user_id = %s", (FAKE_USER_ID,))
    conn.commit()


def main():
    keep = "--keep" in sys.argv

    conn = connect_to_database()
    if not conn:
        print("Could not connect to DB"); return 1

    start_utc, end_utc = get_event_window()
    print(f"Event window: {start_utc.date()} -> {end_utc.date()}")
    print(f"Fake user id: {FAKE_USER_ID}")

    # Always start from a clean slate for this fake user.
    _cleanup(conn)

    try:
        # Phase 1: 7 distinct days
        print("\n--- Phase 1: inserting 7 distinct days ---")
        _insert_fake_logs(conn, list(range(0, 7)))
        days = count_distinct_submission_days(FAKE_USER_ID, start_utc, end_utc)
        print(f"Distinct days counted: {days} (expected 7)")
        awarded = check_and_award_milestones(FAKE_USER_ID)
        keys = [b["key"] for b in awarded]
        print(f"Newly awarded: {keys} (expected ['day7_done'])")
        assert keys == ["day7_done"], "FAIL: day7_done not awarded"

        # Phase 2: idempotency
        print("\n--- Phase 2: re-running check (idempotency) ---")
        awarded2 = check_and_award_milestones(FAKE_USER_ID)
        keys2 = [b["key"] for b in awarded2]
        print(f"Newly awarded on rerun: {keys2} (expected [])")
        assert keys2 == [], "FAIL: idempotency broken"

        # Phase 3: cross 14 days
        print("\n--- Phase 3: adding 7 more distinct days (total 14) ---")
        _insert_fake_logs(conn, list(range(7, 14)))
        days = count_distinct_submission_days(FAKE_USER_ID, start_utc, end_utc)
        print(f"Distinct days counted: {days} (expected 14)")
        awarded3 = check_and_award_milestones(FAKE_USER_ID)
        keys3 = [b["key"] for b in awarded3]
        print(f"Newly awarded: {keys3} (expected ['day14_done'])")
        assert keys3 == ["day14_done"], "FAIL: day14_done not awarded"

        # Final state
        print("\n--- Final badges on file ---")
        for b in list_user_badges(FAKE_USER_ID):
            print(f"  {b['key']:12} {b['name']:14} awarded={b['awarded_at']}")

        print("\n✅ All milestone assertions passed.")
        return 0

    finally:
        if not keep:
            print("\n--- Cleaning up fake user's rows ---")
            _cleanup(conn)
        else:
            print("\n--keep flag set; rows left in DB.")
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
