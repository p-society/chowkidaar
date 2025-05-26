import psycopg2
from utils.parse_message import extract_user_info
import pytz
import datetime
from prometheus_client import Counter
import os
from dotenv import load_dotenv

# Load env variables from .env file
load_dotenv()
DB_URL = os.getenv("NEON_DB_URL")

total_db_operations = Counter('total_db_operations', 'Count of total database ops occured')

def connect_to_database():
    """Central database connection function that tries both connection methods"""
    try:
        if DB_URL:
            try:
                conn = psycopg2.connect(DB_URL)
                print("✅ Connected to Neon DB successfully.")
                return conn
            except Exception as e:
                print(f"Failed to connect to Neon DB: {e}")

    except psycopg2.Error as e:
        print(f"Error connecting to the database: {e}")
        return None

def save_log(message, discord_user_id, discord_message_id, sent_at, in_text_valid=-1):
    try:
        conn = connect_to_database()
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
        conn = connect_to_database()
        cur = conn.cursor()
        cur.execute("""
            UPDATE participation_logs
            SET message = %s, in_text_valid = %s, updated_at = %s
            WHERE discord_message_id = '%s'
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
        conn = connect_to_database()
        cur = conn.cursor()
        ist_time = get_ist_time()
        cur.execute(
            """
            UPDATE participation_logs
            SET deleted_at = %s
            WHERE discord_message_id = '%s'
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
def save_cp_log(student_id, name, solved_questions, day):
    """Save CP log to database"""
    conn = connect_to_database()
    if not conn:
        return


    with conn.cursor() as cur:
        # Make sure user exists
        cur.execute('SELECT * FROM "student_list_2024" WHERE "stu_id" = %s;', (student_id,))
        if cur.fetchone() is None:
            print("❌ User not found")

        # Update solved questions
        try:
            for i in range(len(solved_questions)):
                field = f"q{i + 1}"
                cur.execute(f'''
                    UPDATE student_list_2024
                    SET {field} = array_append({field}, '%s'),
                        all_solved = array_append(all_solved, %s)
                    WHERE stu_id = %s;
                ''', (day, solved_questions[i], student_id))
        except Exception as e:
            print("Error: ", e)

        conn.commit()
        print("✅ Updated CP log successfully.")

def delete_cp_log(student_id, day):
    """Delete CP log from database"""
    conn = connect_to_database()
    if conn is None:
        return

    with conn.cursor() as cur:
        fields = ["q1", "q2", "q3"]
        count_removed = 0

        for field in fields:
            cur.execute(f"""
                SELECT "{field}" FROM "student_list_2024" WHERE "stu_id" = %s;
            """, (student_id,))
            result = cur.fetchone()

            if result and day in result[0]:
                cur.execute(f"""
                    UPDATE "student_list_2024"
                    SET "{field}" = array_remove("{field}", %s),
                        "total_solved" = "total_solved" - 1
                    WHERE "stu_id" = %s;
                """, (day, student_id))
                count_removed += 1

        conn.commit()
        print(f"✅ Deleted '{day}' from {count_removed} field(s) for student '{student_id}'.")

# Utility functions
def get_ist_time():
    utc_now = datetime.datetime.now()
    ist = pytz.timezone('Asia/Kolkata')
    ist_now = utc_now.replace(tzinfo=pytz.utc).astimezone(ist)
    return ist_now

def check_intext_validity(message):
    conn = connect_to_database()
    if not conn:
        print("Failed to connect to database for intext validity check")
        return -1
        
    cur = conn.cursor()
    try: 
        college_id = extract_user_info(message)[0]
        print("Here is your college id", college_id)
        if college_id:
            cur.execute("SELECT name FROM student_list_2024 WHERE stu_id=%s", (college_id,))
            full_name = cur.fetchone()
            print("FUll name is  => ", full_name)
            total_db_operations.inc()
            if full_name:
                first_name = full_name[0].split()[0]
                if first_name.lower() in message.lower():
                    return 1
                elif full_name[0].lower() in message.lower():
                    return 1
            else:
                print(f"No name found for student_id: {college_id}")
        return 0  
    except Exception as e:
        print(f"Error while checking intext validity: {e}")
        return -1
    finally:
        cur.close() 
        conn.close()

def register_user(student_id: str, name: str, lc_handle: str, cf_handle: str) -> bool:
    """
    Register a new user or update their handles.
    
    Args:
        student_id (str): The student's ID
        name (str): The student's full name
        lc_handle (str): The student's LeetCode handle
        cf_handle (str): The student's CodeForces handle
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        conn = connect_to_database()
        if not conn:
            return False
            
        with conn.cursor() as cur:
            # Check if user exists
            cur.execute('SELECT * FROM student_list_2024 WHERE stu_id = %s', (student_id,))
            user = cur.fetchone()
            
            if user:
                # Update existing user
                cur.execute('''
                    UPDATE student_list_2024 
                    SET name = %s, lc_handle = %s, cf_handle = %s
                    WHERE stu_id = %s
                ''', (name, lc_handle, cf_handle, student_id))
            else:
                # Insert new user
                cur.execute('''
                    INSERT INTO student_list_2024 
                    (stu_id, name, lc_handle, cf_handle, q1, q2, q3, all_solved)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ''', (student_id, name, lc_handle, cf_handle, [], [], [], []))
                
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

if __name__ == "__main__":
    print(check_intext_validity(""))
