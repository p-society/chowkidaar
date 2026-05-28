import sys
import os
import datetime
import pytz
import psycopg2

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: F401
from db.db import connect_to_database, save_cp_log, delete_cp_log, get_ist_time
from db.badges import current_streak

def run_test():
    print("--- Streak Deletion & all_solved Array Pruning Verification ---")
    conn = connect_to_database()
    if not conn:
        print("❌ Cannot connect to database")
        return

    fake_student_id = "STU_TEST_9999"
    fake_discord_user_id = 999999999999999999
    test_day = 15

    try:
        with conn.cursor() as cur:
            # Clean up old records
            cur.execute("DELETE FROM student_list_2024 WHERE stu_id = %s;", (fake_student_id,))
            cur.execute("DELETE FROM participation_logs WHERE discord_user_id = %s;", (fake_discord_user_id,))
            cur.execute("DELETE FROM day_brackets WHERE day = %s;", (str(test_day),))
            
            # Setup student
            cur.execute("""
                INSERT INTO student_list_2024 (stu_id, name, discord_user_id, q1, q2, q3, all_solved, total_solved)
                VALUES (%s, 'Test Student', %s, '{}', '{}', '{}', '{}', 0);
            """, (fake_student_id, fake_discord_user_id))
            
            # Setup bracket for day 15
            initial_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
            final_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=2)
            cur.execute("""
                INSERT INTO day_brackets (day, initial_time, final_time)
                VALUES (%s, %s, %s);
            """, (str(test_day), initial_time, final_time))
            
            # Add a fake participation log entry
            cur.execute("""
                INSERT INTO participation_logs (message, discord_user_id, discord_message_id, sent_at, in_text_valid)
                VALUES ('fake submission msg', %s, 999999999999999999, %s, 1);
            """, (fake_discord_user_id, datetime.datetime.now(datetime.timezone.utc)))
            
        conn.commit()

        # Phase 1: Save CP Log
        print("\n[Phase 1] Saving CP Log...")
        save_cp_log(fake_student_id, "Test Student", ["implement-stack-using-queues", "implement-queue-using-stacks"], test_day)
        
        with conn.cursor() as cur:
            cur.execute("SELECT q1, q2, q3, all_solved, total_solved FROM student_list_2024 WHERE stu_id = %s;", (fake_student_id,))
            row = cur.fetchone()
            print(f"After save: q1={row[0]}, q2={row[1]}, q3={row[2]}, all_solved={row[3]}, total_solved={row[4]}")
            assert str(test_day) in row[0], "Day should be in q1"
            assert "implement-stack-using-queues" in row[3] and "implement-queue-using-stacks" in row[3], "Questions should be in all_solved"
            assert row[4] == 2, f"total_solved should be 2, got {row[4]}"

        # Phase 2: Delete CP Log and verify all_solved pruning and participation_logs deletion
        print("\n[Phase 2] Deleting CP Log...")
        delete_cp_log(fake_student_id, test_day)

        with conn.cursor() as cur:
            cur.execute("SELECT q1, q2, q3, all_solved, total_solved FROM student_list_2024 WHERE stu_id = %s;", (fake_student_id,))
            row = cur.fetchone()
            print(f"After delete: q1={row[0]}, q2={row[1]}, q3={row[2]}, all_solved={row[3]}, total_solved={row[4]}")
            assert str(test_day) not in row[0], "Day should be removed from q1"
            assert "implement-stack-using-queues" not in row[3] and "implement-queue-using-stacks" not in row[3], "Stale questions should be removed from all_solved"
            assert row[4] == 0, f"total_solved should be 0, got {row[4]}"

            # Verify participation_logs was marked as deleted
            cur.execute("SELECT deleted_at FROM participation_logs WHERE discord_user_id = %s;", (fake_discord_user_id,))
            deleted_at = cur.fetchone()[0]
            print(f"Participation log deleted_at: {deleted_at}")
            assert deleted_at is not None, "Participation log should be marked as deleted!"

        print("\n✅ Streak deletion and all_solved array pruning verified successfully!")

    finally:
        # Cleanup
        with conn.cursor() as cur:
            cur.execute("DELETE FROM student_list_2024 WHERE stu_id = %s;", (fake_student_id,))
            cur.execute("DELETE FROM participation_logs WHERE discord_user_id = %s;", (fake_discord_user_id,))
            cur.execute("DELETE FROM day_brackets WHERE day = %s;", (str(test_day),))
        conn.commit()
        conn.close()

if __name__ == "__main__":
    run_test()
