from datetime import datetime, time, timedelta
import pytz
from db import connect_to_database
initial = 16
final= 12

def is_in_time_bracket(msg_sending_time):
    ist = pytz.timezone('Asia/Kolkata')
    msg_sending_time_ist = msg_sending_time.astimezone(ist)
    msg_time = msg_sending_time_ist.time()

    start_time = time(initial, 0)
    end_time = time(final, 0)

    if start_time <= msg_time or msg_time <= end_time:
        return True
    return False


def is_unique_in_time_bracket(discord_user_id, msg_sending_time):
    conn = connect_to_database()
    cur = conn.cursor()
    ist = pytz.timezone('Asia/Kolkata')
    
    msg_sending_time_ist = msg_sending_time.astimezone(ist)
    msg_sending_date_ist = msg_sending_time_ist.date()

    bracket_start = ist.localize(datetime.combine(msg_sending_date_ist, time(initial, 0)))
    bracket_end = ist.localize(datetime.combine(msg_sending_date_ist + timedelta(days=1), time(final, 0)))

    print(f"Bracket start: {bracket_start}, Bracket end: {bracket_end}")

    cur.execute("""
        SELECT COUNT(*)
        FROM participation_logs
        WHERE discord_user_id = %s
        AND sent_at >= %s
        AND sent_at < %s
        AND deleted_at IS NULL
    """, (discord_user_id, bracket_start, bracket_end))
    
    result = cur.fetchone()
    cur.close()
    conn.close()

    print(f"Query result: {result}")

    if result[0] > 0:
        return False

    return True

def can_send_message(discord_user_id, msg_sending_time):
    
    print(discord_user_id, msg_sending_time)
    if not is_in_time_bracket(msg_sending_time):
        print("Nahi bhej sakta 1")
        return False

    if not is_unique_in_time_bracket(discord_user_id, msg_sending_time):
        print("Nahi bhej sakta 2")
        return False

    print("bhej sakta")
    return True
