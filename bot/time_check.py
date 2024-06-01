from datetime import datetime, time, timedelta
import pytz
from db import connect_to_database
initial = 15
final= 18

def is_in_time_bracket(msg_sending_time):
    
    ist = pytz.timezone('Asia/Kolkata')
    msg_sending_time_ist = msg_sending_time.astimezone(ist)

    
    start_time = time(initial, 0)  
    end_time = time(final, 0)    
    
    if msg_sending_time_ist.time() >= start_time or msg_sending_time_ist.time() < end_time:
        return True
    return False

def is_unique_in_time_bracket(discord_user_id, msg_sending_time):
    conn = connect_to_database()
    cur = conn.cursor()
    
    ist = pytz.timezone('Asia/Kolkata')
    msg_sending_time_ist = msg_sending_time.astimezone(ist)

    if msg_sending_time_ist.time() >= time(initial, 0):
        bracket_start = msg_sending_time_ist.replace(hour=initial, minute=0, second=0, microsecond=0)
        bracket_end = (bracket_start + timedelta(hours=14)).replace(hour=final, minute=0, second=0, microsecond=0)
    else:
        bracket_start = (msg_sending_time_ist.replace(hour=initial, minute=0, second=0, microsecond=0) - timedelta(days=1))
        bracket_end = msg_sending_time_ist.replace(hour=final, minute=0, second=0, microsecond=0)

    cur.execute("""
        SELECT COUNT(*)
        FROM participation_logs
        WHERE discord_user_id = %s
        AND sent_at >= %s
        AND sent_at < %s
    """, (discord_user_id, bracket_start, bracket_end))
    
    result = cur.fetchone()
    cur.close()

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
