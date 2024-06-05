import psycopg2
from config import DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD, DATABASE_HOST
from parse_message import extract_user_info
import pytz
import datetime
from prometheus_client import Counter

total_db_operations = Counter('total_db_operations', 'Count of total database ops occured')
def connect_to_database():
    try:
        conn = psycopg2.connect(
            dbname=DATABASE_NAME,
            user=DATABASE_USER,
            password=DATABASE_PASSWORD,
            host=DATABASE_HOST,
            port=5432
        )
        print("Connection to the database was successful")
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to the database: {e}")
        return None
    
    
def save_log( message, discord_user_id, discord_message_id, sent_at, in_text_valid=-1):
    try:
        conn = connect_to_database()
        cur = conn.cursor()
        ist = pytz.timezone('Asia/Kolkata')
    
        sent_at_ist = sent_at.astimezone(ist)
        sent_at_date_ist = sent_at_ist.date()

        cur.execute(
            """
            INSERT INTO participation_logs (
                message, discord_user_id, discord_message_id, sent_at, in_text_valid
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (message, discord_user_id, discord_message_id, sent_at_date_ist, in_text_valid)
        )
        conn.commit()
        total_db_operations.inc()
    except psycopg2.Error as e:
        print(f"Error occurred while saving log: {e}")
        conn.rollback()  # Rollback the transaction if there is any error
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
            WHERE discord_message_id = %s
        """, (message, in_text_valid, updated_at, discord_message_id))
        conn.commit()
        total_db_operations.inc()
        if cur.rowcount == 0:
            conn.rollback()  # Rollback the transaction if no rows were updated
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

def get_ist_time():
    utc_now = datetime.datetime.now()
    ist = pytz.timezone('Asia/Kolkata')
    ist_now = utc_now.replace(tzinfo=pytz.utc).astimezone(ist)
    return ist_now

def delete_log(discord_message_id):
    try:
        conn = connect_to_database()
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

def check_intext_validity( message):
    conn = connect_to_database()
    cur = conn.cursor()
    try: 
        college_id = extract_user_info(message)
        if college_id:
            cur.execute("SELECT name FROM student_list_2023 WHERE student_id = %s", (college_id.upper(),))
            full_name = cur.fetchone()
            total_db_operations.inc()
            if full_name:
                first_name = full_name[0].split()[0]  # Assuming name is the first element of the tuple
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
    

if __name__ == "__main__":
    print(check_intext_validity( ""))