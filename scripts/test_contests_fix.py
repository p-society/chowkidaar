"""
Test script to validate the contest bug fixes.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

# Allow importing db and integrations from this script
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa
from db.db import connect_to_database
from db.badges import list_user_badges
from db.contests import record_user_contests
from integrations.contest_types import ContestEntry
from integrations.leetcode_contests import fetch_user_contests

FAKE_USER_ID = 888888888888888888


def test_leetcode_delta_calculation():
    print("--- Test 1: LeetCode Delta Calculation ---")
    
    # Mock GraphQL history data
    mock_history = [
        {
            "attended": True,
            "rating": 1620.5,
            "ranking": 45,
            "contest": {
                "title": "Weekly Contest 1",
                "titleSlug": "weekly-contest-1",
                "startTime": 1000000
            }
        },
        {
            "attended": False,
            "rating": 1620.5,
            "ranking": 0,
            "contest": {
                "title": "Weekly Contest 2",
                "titleSlug": "weekly-contest-2",
                "startTime": 1010000
            }
        },
        {
            "attended": True,
            "rating": 1590.2,
            "ranking": 200,
            "contest": {
                "title": "Weekly Contest 3",
                "titleSlug": "weekly-contest-3",
                "startTime": 1020000
            }
        },
        {
            "attended": True,
            "rating": 1640.8,
            "ranking": 90,
            "contest": {
                "title": "Weekly Contest 4",
                "titleSlug": "weekly-contest-4",
                "startTime": 1030000
            }
        }
    ]

    with patch("integrations.leetcode_contests._post") as mock_post:
        mock_post.return_value = {"userContestRankingHistory": mock_history}
        
        # Test only_attended = True
        entries = fetch_user_contests("test_user", only_attended=True)
        
        assert len(entries) == 3, f"Expected 3 attended entries, got {len(entries)}"
        
        # Weekly Contest 1: rating 1620.5, prev 1500.0 => delta = 1620.5 - 1500.0 = 120.5 => 120
        assert entries[0].contest_name == "Weekly Contest 1"
        assert entries[0].rating_delta == 120, f"Expected delta 120, got {entries[0].rating_delta}"
        assert entries[0].rank == 45
        
        # Weekly Contest 3: rating 1590.2, prev 1620.5 => delta = 1590.2 - 1620.5 = -30.3 => -30
        assert entries[1].contest_name == "Weekly Contest 3"
        assert entries[1].rating_delta == -30, f"Expected delta -30, got {entries[1].rating_delta}"
        assert entries[1].rank == 200
        
        # Weekly Contest 4: rating 1640.8, prev 1590.2 => delta = 1640.8 - 1590.2 = 50.6 => 51
        assert entries[2].contest_name == "Weekly Contest 4"
        assert entries[2].rating_delta == 51, f"Expected delta 51, got {entries[2].rating_delta}"
        assert entries[2].rank == 90

        print("✅ LeetCode rating delta calculations are correct!")


def setup_db_fake_user(conn):
    with conn.cursor() as cur:
        # Clean up existing test data
        cur.execute("DELETE FROM user_badges WHERE discord_user_id = %s", (FAKE_USER_ID,))
        cur.execute("DELETE FROM contest_attendance WHERE discord_user_id = %s", (FAKE_USER_ID,))
        cur.execute("DELETE FROM student_list_2024 WHERE stu_id = 'test_stu_id'")
        
        # Insert student record
        cur.execute(
            """
            INSERT INTO student_list_2024 (stu_id, name, lc_handle, cf_handle, discord_user_id)
            VALUES ('test_stu_id', 'Test Student', 'test_lc', 'test_cf', %s)
            """,
            (FAKE_USER_ID,)
        )
    conn.commit()


def cleanup_db(conn):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM user_badges WHERE discord_user_id = %s", (FAKE_USER_ID,))
        cur.execute("DELETE FROM contest_attendance WHERE discord_user_id = %s", (FAKE_USER_ID,))
        cur.execute("DELETE FROM student_list_2024 WHERE stu_id = 'test_stu_id'")
    conn.commit()


async def test_db_upsert_and_badges():
    print("\n--- Test 2: Database Upsert and Badges ---")
    conn = connect_to_database()
    if not conn:
        print("Failed to connect to database for DB test")
        return
        
    setup_db_fake_user(conn)
    
    try:
        # 1. Simulate an early poll: insert a contest with None rank/rating_delta
        start_utc, end_utc = datetime.now(timezone.utc) - timedelta(days=2), datetime.now(timezone.utc) + timedelta(days=5)
        contest_date = datetime.now(timezone.utc) - timedelta(days=1)
        
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO contest_attendance
                    (discord_user_id, platform, contest_id, contest_name, contest_date, rank, rating_delta, points_awarded)
                VALUES (%s, 'leetcode', 'weekly-contest-99', 'Weekly Contest 99', %s, NULL, NULL, 10)
                """,
                (FAKE_USER_ID, contest_date)
            )
        conn.commit()
        
        # Verify initial state in DB
        with conn.cursor() as cur:
            cur.execute("SELECT rank, rating_delta FROM contest_attendance WHERE discord_user_id = %s", (FAKE_USER_ID,))
            row = cur.fetchone()
            assert row[0] is None and row[1] is None, f"Expected NULLs, got {row}"
            
        print("Inserted initial contest with NULL rank and rating_delta")

        # 2. Mock API fetching returning finalized values (rank 80, rating_delta +40)
        mock_lc_entry = ContestEntry(
            platform="leetcode",
            contest_id="weekly-contest-99",
            contest_name="Weekly Contest 99",
            contest_date=contest_date,
            rank=80,
            rating_delta=40,
            attended=True
        )

        with patch("db.contests.get_event_window", return_value=(start_utc, end_utc)), \
             patch("db.contests._fetch_lc", return_value=[mock_lc_entry]), \
             patch("db.contests._fetch_cf", return_value=[]):
             
             # Call record_user_contests. It should do DO UPDATE and award badges.
             newly_recorded, awarded_badges = await record_user_contests(FAKE_USER_ID)
             
             # Check if newly_recorded is empty (since it was already in DB, it is not new for points)
             assert len(newly_recorded) == 0, f"Expected 0 newly_recorded (already exists), got {len(newly_recorded)}"
             
             # Verify database updated the rank and rating_delta
             with conn.cursor() as cur:
                 cur.execute("SELECT rank, rating_delta FROM contest_attendance WHERE discord_user_id = %s", (FAKE_USER_ID,))
                 row = cur.fetchone()
                 assert row[0] == 80, f"Expected rank 80, got {row[0]}"
                 assert row[1] == 40, f"Expected rating_delta 40, got {row[1]}"
                 
             print("Database successfully upserted rank and rating_delta columns!")

             # Verify badges were awarded
             badges = list_user_badges(FAKE_USER_ID)
             badge_keys = {b["key"] for b in badges}
             
             print(f"Badges awarded: {badge_keys}")
             assert "contest_participant" in badge_keys, "Expected contest_participant badge"
             assert "contest_top_100" in badge_keys, "Expected contest_top_100 badge (rank 80)"
             assert "contest_rating_climber" in badge_keys, "Expected contest_rating_climber badge (delta +40)"
             
             print("✅ Database upserts and badge awarding fixes verified successfully!")
             
    finally:
        cleanup_db(conn)
        conn.close()


def main():
    test_leetcode_delta_calculation()
    
    import asyncio
    asyncio.run(test_db_upsert_and_badges())


if __name__ == "__main__":
    main()
