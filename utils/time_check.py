import logging as logger
from datetime import datetime, time, timedelta

from db.db import check_time_bracket, connect_to_database, get_bracket_range_db
from prometheus_client import Counter

INITIAL = time(16,30)
FINAL = time(6,30)


messages_rejected_total_TIME = Counter(
    "discord_messages_rejected_total_TIME",
    "Total number of messages rejected due to time check invalidations",
)
messages_rejected_total_DUPLICATE = Counter(
    "discord_messages_rejected_total_DUPLICATE",
    "Total number of messages rejected due to duplicate messages in one time frame",
)


def is_in_time_bracket(day, msg_timestamp):
    return check_time_bracket(day, msg_timestamp)


def is_unique_in_time_bracket(discord_user_id, msg_timestamp, day):
    conn = connect_to_database()
    cur = conn.cursor()

    bracket_start, bracket_end = get_bracket_range(msg_timestamp, day)

    cur.execute(
        """
        SELECT COUNT(*)
        FROM participation_logs
        WHERE discord_user_id = '%s'
        AND sent_at >= %s
        AND sent_at < %s
        AND deleted_at IS NULL
    """,
        (discord_user_id, str(bracket_start), str(bracket_end)),
    )

    result = cur.fetchone()
    cur.close()
    conn.close()


    if result[0] > 0:
        messages_rejected_total_DUPLICATE.inc()
        logger.warning(
            f"is unique in time bracket check failed for message sent at : {msg_timestamp} sent by discord_user_id: {discord_user_id} ",
            extra={"tags": {"event": "on_message"}},
        )
        return False
    return True

def get_bracket_range(msg_timestamp, day):
    msg_sending_time= msg_timestamp.time() 
    msg_sending_date = msg_timestamp.date()
    initial, final = get_bracket_range_db(day)
    # last second of a day aka the largest possible second of a day
    midnight = time(23,59,59,999999)

    if INITIAL <= msg_sending_time <= midnight:
        start_date = msg_sending_date
        end_date = msg_sending_date + timedelta(days=1)
    else:
        start_date = msg_sending_date - timedelta(days=1)
        end_date = msg_sending_date 

    bracket_start = datetime.combine(start_date, INITIAL)
    bracket_end = datetime.combine(end_date, FINAL)

    return bracket_start, bracket_end


def can_send_message(discord_user_id, msg_sending_time, day):

    if not is_in_time_bracket(day, msg_sending_time):
        return False

    if not is_unique_in_time_bracket(discord_user_id, msg_sending_time, day):
        return False
    logger.info(
        f"all time checks passed for message sent at : {msg_sending_time} sent by discord_user_id: {discord_user_id} ",
        extra={"tags": {"event": "on_message"}},
    )
    return True


if __name__ == "__main__":
    msg_timestamp = datetime.strptime("2021-06-04 06:40:20.000000", "%Y-%m-%d %H:%M:%S.%f")
    start, end = get_bracket_range(msg_timestamp)
    print(start, end)
