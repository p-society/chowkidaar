"""
Persistent dedup for contest-start reminders.

The reminder loop in cogs/contests.py used to keep an in-memory set of
(contest_url, reminder_type) tuples to avoid double-sending. That set was
lost on every bot restart, so restarting during a reminder window (12 h
before contest start is a 1-hour window!) would re-ping @CONTEST_ROLE.

This module backs the dedup with a small Postgres table so reminders fire
exactly once per (contest, reminder_kind) even across restarts.

Public surface:
    was_sent(contest_url, reminder_type) -> bool
    mark_sent(contest_url, reminder_type) -> bool
        Idempotent INSERT; returns True if this call actually inserted the row
        (i.e. caller is the first to send this reminder), False if a row
        already existed (someone else got there first — caller should NOT
        send the reminder).
    prune_older_than(days) -> int
        Housekeeping; removes rows older than `days`. Returns row count.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import psycopg2

from db.db import connect_to_database, total_db_operations


def was_sent(contest_url: str, reminder_type: str, conn=None) -> bool:
    """True if we already recorded sending this (contest_url, reminder_type)."""
    should_close = False
    if not conn:
        conn = connect_to_database(purpose="Check if Reminder Sent")
        should_close = True
    if not conn:
        # DB down: be cautious — claim it's not sent so the caller will
        # attempt it. The mark_sent INSERT will fail the same way, so we
        # won't double-send if the DB stays down; if the DB comes back
        # between checks we accept a small duplicate risk.
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM contest_reminders_sent
                WHERE contest_url = %s AND reminder_type = %s
                LIMIT 1
                """,
                (contest_url, reminder_type),
            )
            return cur.fetchone() is not None
    except psycopg2.errors.UndefinedTable:
        # Pre-migration — degrade to "never sent" so the in-memory set in
        # the caller still has a chance to dedupe within a single run.
        return False
    except psycopg2.Error as e:
        logging.error(f"was_sent error: {e}")
        return False
    finally:
        if should_close:
            conn.close()


def mark_sent(contest_url: str, reminder_type: str, conn=None) -> bool:
    """
    Idempotent INSERT. Returns True iff this call actually inserted the row.

    The caller's pattern should be:

        if mark_sent(url, kind):
            await channel.send(...)

    so that the reminder is sent exactly once even under concurrent loop
    iterations or rapid restarts.
    """
    should_close = False
    if not conn:
        conn = connect_to_database(purpose="Mark Reminder Sent")
        should_close = True
    if not conn:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO contest_reminders_sent (contest_url, reminder_type)
                VALUES (%s, %s)
                ON CONFLICT (contest_url, reminder_type) DO NOTHING
                RETURNING contest_url
                """,
                (contest_url, reminder_type),
            )
            inserted = cur.fetchone() is not None
            conn.commit()
            total_db_operations.inc()
            return inserted
    except psycopg2.errors.UndefinedTable:
        # Pre-migration — fall back to "claim we inserted" so the reminder
        # still fires; without the table we can't dedupe across restarts but
        # the in-memory set in the cog still helps within a session.
        logging.warning(
            "contest_reminders_sent missing — run scripts/init_contest_reminders.py"
        )
        return True
    except psycopg2.Error as e:
        logging.error(f"mark_sent error: {e}")
        conn.rollback()
        return False
    finally:
        if should_close:
            conn.close()


def prune_older_than(days: int = 30) -> int:
    """Delete reminder rows older than `days`. Returns rows deleted."""
    conn = connect_to_database(purpose="Prune Old Reminders")
    if not conn:
        return 0
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM contest_reminders_sent WHERE sent_at < %s",
                (cutoff,),
            )
            n = cur.rowcount
            conn.commit()
            return n
    except psycopg2.errors.UndefinedTable:
        return 0
    except psycopg2.Error as e:
        logging.error(f"prune_older_than error: {e}")
        conn.rollback()
        return 0
    finally:
        conn.close()
