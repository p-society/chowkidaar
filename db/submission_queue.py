"""
Submission Queue — PostgreSQL-backed queue for retrying failed /submit commands.

When an external API (Codeforces, LeetCode) is down during /submit, the
submission is enqueued here and retried automatically by the queue_processor
cog every 2 hours, up to 6 times (12 hours total).
"""

import logging
from db.db import connect_to_database

logger = logging.getLogger(__name__)


def enqueue_submission(
    user_id: str,
    discord_user_id: int,
    day: int,
    description: str,
    submitted_at,
    failed_platform: str,
    error_msg: str | None = None,
) -> bool:
    """Insert a pending submission into the queue.

    Uses ON CONFLICT DO NOTHING so duplicate (user_id, day, 'pending')
    entries are silently ignored.

    Returns True if a row was inserted, False otherwise.
    """
    conn = connect_to_database(purpose="Enqueue Submission")
    if not conn:
        logger.error("enqueue_submission: could not connect to database")
        return False

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO submission_queue
                    (user_id, discord_user_id, day, description, submitted_at,
                     failed_platform, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id, day, status) DO NOTHING
                """,
                (user_id, discord_user_id, day, description, submitted_at,
                 failed_platform, error_msg),
            )
            conn.commit()
            inserted = cur.rowcount > 0
            if inserted:
                logger.info(
                    f"Enqueued submission: user={user_id} day={day} "
                    f"platform={failed_platform}"
                )
            return inserted
    except Exception as e:
        logger.error(f"enqueue_submission error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def get_pending_jobs() -> list[dict]:
    """Fetch all pending jobs whose next_retry_at has passed.

    Returns a list of dicts with all queue columns.
    """
    conn = connect_to_database(purpose="Fetch Pending Queue Jobs")
    if not conn:
        return []

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, discord_user_id, day, description,
                       submitted_at, failed_platform, retry_count, max_retries,
                       error_message
                FROM submission_queue
                WHERE status = 'pending'
                  AND next_retry_at <= NOW()
                ORDER BY queued_at ASC
                """
            )
            columns = [
                "id", "user_id", "discord_user_id", "day", "description",
                "submitted_at", "failed_platform", "retry_count", "max_retries",
                "error_message",
            ]
            return [dict(zip(columns, row)) for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"get_pending_jobs error: {e}")
        return []
    finally:
        conn.close()


def mark_processed(job_id: int) -> None:
    """Mark a queued job as successfully processed."""
    conn = connect_to_database(purpose="Mark Queue Job Processed")
    if not conn:
        return

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE submission_queue
                SET status = 'processed'
                WHERE id = %s
                """,
                (job_id,),
            )
            conn.commit()
            logger.info(f"Queue job {job_id} marked as processed")
    except Exception as e:
        logger.error(f"mark_processed error: {e}")
        conn.rollback()
    finally:
        conn.close()


def mark_retry(job_id: int) -> None:
    """Increment retry count and push next_retry_at forward by 2 hours."""
    conn = connect_to_database(purpose="Mark Queue Job Retry")
    if not conn:
        return

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE submission_queue
                SET retry_count = retry_count + 1,
                    next_retry_at = NOW() + INTERVAL '2 hours'
                WHERE id = %s
                """,
                (job_id,),
            )
            conn.commit()
            logger.info(f"Queue job {job_id} scheduled for retry")
    except Exception as e:
        logger.error(f"mark_retry error: {e}")
        conn.rollback()
    finally:
        conn.close()


def mark_failed(job_id: int, error_msg: str | None = None) -> None:
    """Mark a queued job as permanently failed (dead letter)."""
    conn = connect_to_database(purpose="Mark Queue Job Failed")
    if not conn:
        return

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE submission_queue
                SET status = 'failed',
                    error_message = COALESCE(%s, error_message)
                WHERE id = %s
                """,
                (error_msg, job_id),
            )
            conn.commit()
            logger.info(f"Queue job {job_id} marked as failed (dead letter)")
    except Exception as e:
        logger.error(f"mark_failed error: {e}")
        conn.rollback()
    finally:
        conn.close()


def update_queued_description(user_id: str, day: int, new_description: str) -> bool:
    """Update the description of a pending queue entry (for /edit_submission).

    Returns True if a row was updated.
    """
    conn = connect_to_database(purpose="Update Queued Description")
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE submission_queue
                SET description = %s
                WHERE user_id = %s AND day = %s AND status = 'pending'
                """,
                (new_description, user_id, day),
            )
            conn.commit()
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"update_queued_description error: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def has_pending_entry(user_id: str, day: int) -> bool:
    """Check if a pending queue entry exists for this user and day."""
    conn = connect_to_database(purpose="Check Pending Queue Entry")
    if not conn:
        return False

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1 FROM submission_queue
                WHERE user_id = %s AND day = %s AND status = 'pending'
                LIMIT 1
                """,
                (user_id, day),
            )
            return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"has_pending_entry error: {e}")
        return False
    finally:
        conn.close()
