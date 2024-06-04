from datetime import datetime, time, timedelta
import pytz
from db import connect_to_database
from prometheus_client import Counter 
from loki_logger import logger
INITIAL = 18
FINAL= 12


messages_rejected_total_TIME = Counter('discord_messages_rejected_total_TIME', 'Total number of messages rejected due to time check invalidations')
messages_rejected_total_DUPLICATE = Counter('discord_messages_rejected_total_DUPLICATE', 'Total number of messages rejected due to duplicate messages in one time frame')

def is_in_time_bracket(discord_user_id,msg_sending_time):
    ist = pytz.timezone('Asia/Kolkata')
    msg_sending_time_ist = msg_sending_time.astimezone(ist)
    msg_time = msg_sending_time_ist.time()

    start_time = time(INITIAL, 0)
    end_time = time(FINAL, 0)

    if start_time <= msg_time or msg_time <= end_time:
        return True
    messages_rejected_total_TIME.inc()
    logger.warning(f"is in time bracket check failed for message sent at : {msg_sending_time} sent by discord_user_id: {discord_user_id} ",extra={"tags": {"event": "on_message"}})
    return False


def is_unique_in_time_bracket(discord_user_id, msg_sending_time):
    conn = connect_to_database()
    cur = conn.cursor()
    ist = pytz.timezone('Asia/Kolkata')
    
    msg_sending_time_ist = msg_sending_time.astimezone(ist)
    msg_sending_date_ist = msg_sending_time_ist.date()

    bracket_start = ist.localize(datetime.combine(msg_sending_date_ist, time(INITIAL, 0)))
    bracket_end = ist.localize(datetime.combine(msg_sending_date_ist + timedelta(days=1), time(FINAL, 0)))

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
        messages_rejected_total_DUPLICATE.inc()
        logger.warning(f"is unique in time bracket check failed for message sent at : {msg_sending_time} sent by discord_user_id: {discord_user_id} ",extra={"tags": {"event": "on_message"}})
        return False
    return True

def can_send_message(discord_user_id, msg_sending_time):
    
    if not is_in_time_bracket(discord_user_id,msg_sending_time):
        return False

    if not is_unique_in_time_bracket(discord_user_id, msg_sending_time):
        return False
    logger.info(f"all time checks passed for message sent at : {msg_sending_time} sent by discord_user_id: {discord_user_id} ",extra={"tags": {"event": "on_message"}})
    return True
