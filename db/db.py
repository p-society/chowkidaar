import psycopg2
import pytz
import datetime
from prometheus_client import Counter
import os
from dotenv import load_dotenv

# Load env variables from .env file
load_dotenv()
DB_URL = os.getenv("NEON_DB_URL")

total_db_operations = Counter('total_db_operations', 'Count of total database ops occured')

def connect_to_database(purpose: str = None):
    """Central database connection function that tries both connection methods"""
    try:
        if DB_URL:
            try:
                conn = psycopg2.connect(DB_URL)
                if purpose:
                    print(f"🔌 Connected to Neon DB ({purpose})")
                else:
                    print("✅ Connected to Neon DB successfully.")
                return conn
            except Exception as e:
                print(f"Failed to connect to Neon DB: {e}")

    except psycopg2.Error as e:
        print(f"Error connecting to the database: {e}")
        return None

def get_student_profile(discord_user_id):
    """Return (stu_id, name, total_solved) for the given Discord user, or None.

    Convenience for /card and similar commands that need the full student
    record by Discord ID in one query.
    """
    conn = None
    try:
        conn = connect_to_database(purpose="Fetch Student Profile")
        if not conn:
            return None
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT stu_id, name, COALESCE(total_solved, 0)
                FROM student_list_2024
                WHERE discord_user_id = %s
                LIMIT 1
                """,
                (discord_user_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return {"stu_id": row[0], "name": row[1], "total_solved": int(row[2] or 0)}
    except psycopg2.Error as e:
        print(f"get_student_profile error: {e}")
        return None
    finally:
        if conn:
            conn.close()


def get_registered_name(discord_user_id):
    """Return the registered name for this Discord user, or None if not registered.

    Looks up `student_list_2024.name` by `discord_user_id`. Used to display
    cohort-side identity (e.g. "Aman Raj") rather than the Discord nickname.
    """
    conn = None
    try:
        conn = connect_to_database(purpose="Fetch Registered Name")
        if not conn:
            return None
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name FROM student_list_2024 WHERE discord_user_id = %s LIMIT 1",
                (discord_user_id,),
            )
            row = cur.fetchone()
            return row[0] if row else None
    except psycopg2.Error as e:
        print(f"get_registered_name error: {e}")
        return None
    finally:
        if conn:
            conn.close()


def save_log(message, discord_user_id, discord_message_id, sent_at, in_text_valid=-1):
    try:
        conn = connect_to_database(purpose="Save Discord Message Log")
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO participation_logs (
                message, discord_user_id, discord_message_id, sent_at, in_text_valid
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (message, discord_user_id, discord_message_id, sent_at, in_text_valid)
        )
        conn.commit()
        total_db_operations.inc()
    except psycopg2.Error as e:
        print(f"Error occurred while saving log: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def update_log(discord_message_id, message, in_text_valid, updated_at):
    try:
        conn = connect_to_database(purpose="Update Discord Message Log")
        cur = conn.cursor()
        cur.execute("""
            UPDATE participation_logs
            SET message = %s, in_text_valid = %s, updated_at = %s
            WHERE discord_message_id = %s
        """, (message, in_text_valid, updated_at, discord_message_id))
        conn.commit()
        total_db_operations.inc()
        if cur.rowcount == 0:
            conn.rollback()
            print(f"No log found for message ID: {discord_message_id}")
            return False
        else:
            return True
    except Exception as e:
        print(f"Error updating log: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

def delete_log(discord_message_id):
    try:
        conn = connect_to_database(purpose="Delete Discord Message Log")
        cur = conn.cursor()
        ist_time = get_ist_time()
        cur.execute(
            """
            UPDATE participation_logs
            SET deleted_at = %s
            WHERE discord_message_id = %s
            """,
            (ist_time, discord_message_id),
        )
        conn.commit()
        print(f"Log marked as deleted for message ID: {discord_message_id}")
        total_db_operations.inc()
    except Exception as e:
        print(f"Error updating log: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

# CP logs related functions
def _get_day_question_ids(day):
    try:
        import json
        questions_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "questions.json")
        with open(questions_file, "r") as file:
            questions = json.load(file)
        day_questions = questions.get(str(day)) or []
        ids = []
        for q in day_questions:
            if q.startswith("LC") or q.startswith("CF"):
                ids.append(q[3:])
            else:
                ids.append(q)
        return ids
    except Exception as e:
        print(f"Error loading day questions: {e}")
        return []

def save_cp_log(student_id, name, solved_questions, day):
    """Save CP log to database, cleaning up any existing log for this day first."""
    conn = connect_to_database(purpose="Save CP Submission Log")
    if not conn:
        return

    try:
        with conn.cursor() as cur:
            # 1. Check if user exists
            cur.execute('SELECT 1 FROM student_list_2024 WHERE stu_id = %s;', (student_id,))
            if cur.fetchone() is None:
                print("❌ User not found")
                return

            # 2. Clean up any existing submission for this day from q1, q2, q3
            # and decrement total_solved accordingly.
            day_question_ids = _get_day_question_ids(day)
            fields = ["q1", "q2", "q3"]
            for field in fields:
                cur.execute(f'SELECT "{field}" FROM student_list_2024 WHERE stu_id = %s;', (student_id,))
                res = cur.fetchone()
                if res and res[0] and str(day) in res[0]:
                    cur.execute(f'''
                        UPDATE student_list_2024
                        SET "{field}" = array_remove("{field}", %s),
                            total_solved = GREATEST(COALESCE(total_solved, 0) - 1, 0)
                        WHERE stu_id = %s;
                    ''', (str(day), student_id))

            # Remove any of this day's question IDs from all_solved array to prevent duplicate accumulation
            for q_id in day_question_ids:
                cur.execute('''
                    UPDATE student_list_2024
                    SET all_solved = array_remove(all_solved, %s)
                    WHERE stu_id = %s;
                ''', (q_id, student_id))

            # 3. Append the new solved questions and increment total_solved
            # First, clean any potential duplicates to be absolutely safe:
            for q_id in solved_questions:
                cur.execute('''
                    UPDATE student_list_2024
                    SET all_solved = array_remove(all_solved, %s)
                    WHERE stu_id = %s;
                ''', (q_id, student_id))

            for i in range(min(len(solved_questions), 3)):
                field = f"q{i + 1}"
                cur.execute(f'''
                    UPDATE student_list_2024
                    SET {field} = array_append({field}, %s),
                        all_solved = array_append(all_solved, %s),
                        total_solved = COALESCE(total_solved, 0) + 1
                    WHERE stu_id = %s;
                ''', (str(day), solved_questions[i], student_id))

            conn.commit()
            print("✅ Updated CP log successfully.")
    except Exception as e:
        print(f"Error in save_cp_log: {e}")
        conn.rollback()
    finally:
        conn.close()

def delete_cp_log(student_id, day):
    """Delete CP log from database"""
    conn = connect_to_database(purpose="Delete CP Submission Log")
    if conn is None:
        return

    try:
        with conn.cursor() as cur:
            fields = ["q1", "q2", "q3"]
            count_removed = 0

            for field in fields:
                cur.execute(f"""
                    SELECT "{field}" FROM "student_list_2024" WHERE "stu_id" = %s;
                """, (student_id,))
                result = cur.fetchone()

                if result and str(day) in result[0]:
                    cur.execute(f"""
                        UPDATE "student_list_2024"
                        SET "{field}" = array_remove("{field}", %s),
                            "total_solved" = GREATEST("total_solved" - 1, 0)
                        WHERE "stu_id" = %s;
                    """, (str(day), student_id))
                    count_removed += 1

            # Remove question IDs from all_solved array
            day_question_ids = _get_day_question_ids(day)
            for q_id in day_question_ids:
                cur.execute('''
                    UPDATE student_list_2024
                    SET all_solved = array_remove(all_solved, %s)
                    WHERE stu_id = %s;
                ''', (q_id, student_id))

            # Deletion Streak Fix: find matching participation_logs entry and mark it as deleted
            cur.execute("SELECT discord_user_id FROM student_list_2024 WHERE stu_id = %s;", (student_id,))
            user_row = cur.fetchone()
            if user_row and user_row[0]:
                discord_user_id = user_row[0]
                cur.execute("SELECT initial_time, final_time FROM day_brackets WHERE day = %s;", (str(day),))
                bracket = cur.fetchone()
                if bracket:
                    initial_time, final_time = bracket[0], bracket[1]
                    cur.execute(
                        """
                        UPDATE participation_logs
                        SET deleted_at = %s
                        WHERE discord_user_id = %s
                          AND sent_at >= %s
                          AND sent_at <= %s
                          AND deleted_at IS NULL
                        """,
                        (get_ist_time(), discord_user_id, initial_time, final_time)
                    )

            conn.commit()
            print(f"✅ Deleted '{day}' from {count_removed} field(s) for student '{student_id}'.")
    except Exception as e:
        print(f"Error in delete_cp_log: {e}")
        conn.rollback()
    finally:
        conn.close()

# Utility functions
def get_ist_time():
    return datetime.datetime.now(datetime.timezone.utc).astimezone(pytz.timezone('Asia/Kolkata'))

def register_user(
    student_id: str,
    name: str,
    lc_handle: str,
    cf_handle: str,
    discord_user_id: int | None = None,
) -> bool:
    """
    Register a new user or update their handles.

    Args:
        student_id (str): The student's ID
        name (str): The student's full name
        lc_handle (str): The student's LeetCode handle
        cf_handle (str): The student's CodeForces handle
        discord_user_id (int, optional): The Discord user ID of the person
            running /register. When supplied, it's stored on the row so the
            bot can later map stu_id <-> Discord user for badges and contests.

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = connect_to_database(purpose="Register User")
        if not conn:
            return False

        with conn.cursor() as cur:
            # Check if user exists
            cur.execute('SELECT * FROM student_list_2024 WHERE stu_id = %s', (student_id,))
            user = cur.fetchone()

            if user:
                # Update existing user. COALESCE keeps the stored discord_user_id
                # if it's already set and the caller didn't pass a new one.
                cur.execute('''
                    UPDATE student_list_2024
                    SET name = %s,
                        lc_handle = %s,
                        cf_handle = %s,
                        discord_user_id = COALESCE(%s, discord_user_id)
                    WHERE stu_id = %s
                ''', (name, lc_handle, cf_handle, discord_user_id, student_id))
            else:
                # Insert new user
                cur.execute('''
                    INSERT INTO student_list_2024
                    (stu_id, name, lc_handle, cf_handle, q1, q2, q3, all_solved, discord_user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ''', (student_id, name, lc_handle, cf_handle, [], [], [], [], discord_user_id))
                
            conn.commit()
            total_db_operations.inc()
            return True
            
    except Exception as e:
        print(f"Error registering user: {e}")
        if conn:
            conn.rollback()
        return False
    finally:
        if conn:
            conn.close()


def check_time_bracket(day, timestamp):
    try:
        conn = connect_to_database(purpose="Check Time Bracket")
        if not conn:
            raise Exception
        with conn.cursor() as cur:
            # Check if the timestamp is present in timebracket for the day.
            cur.execute('''
                SELECT *
                FROM day_brackets 
                WHERE day = '%s'
                AND %s BETWEEN initial_time AND final_time;
            ''', (day, timestamp)
            )

            result = cur.fetchone()
            cur.close()
            conn.close()
            if not result:
               return False 
            return True


    except Exception as e:
        print("Error in check_time_bracket", e)


def flag_late(stu_id):
    '''
    Just flagging a student late if he msgs late.
    '''
    conn = connect_to_database(purpose="Mark Late Submission")
    if not conn:
        raise Exception
    with conn.cursor() as cur:
        cur.execute('''
            UPDATE student_list_2024
            SET is_late=True
            WHERE stu_id=%s
        ''', (stu_id,))
    conn.commit()
    return 


def get_bracket_range_db(day):
    '''
    Just returns INITIAL and FINAL time bracket values
    '''
    conn = connect_to_database(purpose="Fetch Time Bracket Range")
    if not conn:
        raise Exception
    with conn.cursor() as cur:
        cur.execute('''
            SELECT initial_time, final_time 
            FROM day_brackets
            WHERE day=%s
        ''', (str(day),)
        )
        result = cur.fetchone()
        if result:
            return result[0], result[1]
        return None


if __name__ == "__main__":
    pass
