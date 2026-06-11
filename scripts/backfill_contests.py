"""
One-off backfill for contest attendance that was missed while the LeetCode
fetch was broken (bot User-Agent → Cloudflare 403 → silently recorded 0).

What it does, per targeted user:
  1. Resets `last_contest_poll_at` to NULL so the per-user poll gate falls
     through to the "first-ever poll" path and re-scans the whole event
     window (instead of short-circuiting on the stale timestamp).
  2. Calls the normal `record_user_contests(...)` path, so missed contests
     are inserted AND contest_participant / contest_rating_climber badges and
     points are awarded exactly as they would have been originally.

Idempotent: re-running is safe (UNIQUE(discord_user_id, platform, contest_id)
+ ON CONFLICT, and badge awards are idempotent).

Usage:
    # one user
    uv run --python 3.12 scripts/backfill_contests.py local --user 123456789012345678

    # everyone who has a LeetCode and/or Codeforces handle
    uv run --python 3.12 scripts/backfill_contests.py local --all

    # 'local' (default) or 'neon' selects the environment, same as other scripts.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: F401  (loads env / .env.* based on argv[1])
from db.db import connect_to_database
from db.contests import record_user_contests


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill missed contest attendance.")
    # argv[1] may be the env name ('local'/'neon') consumed by config.py; accept
    # and ignore it here so argparse doesn't choke on it.
    parser.add_argument("env", nargs="?", default="local", help="local | neon")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--user", type=int, help="Single discord_user_id to backfill.")
    group.add_argument("--all", action="store_true", help="Backfill every registered user.")
    return parser.parse_args()


def _target_user_ids(single_user: int | None) -> list[int]:
    if single_user is not None:
        return [single_user]
    conn = connect_to_database(purpose="Backfill: list registered users")
    if not conn:
        print("ERROR: could not connect to database.")
        return []
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT discord_user_id
                FROM student_list_2024
                WHERE discord_user_id IS NOT NULL
                  AND (NULLIF(TRIM(lc_handle), '') IS NOT NULL
                       OR NULLIF(TRIM(cf_handle), '') IS NOT NULL)
                """
            )
            return [row[0] for row in cur.fetchall()]
    finally:
        conn.close()


def _reset_poll_gate(discord_user_ids: list[int]) -> None:
    """NULL out last_contest_poll_at so the next poll does a full re-scan."""
    conn = connect_to_database(purpose="Backfill: reset poll gate")
    if not conn:
        print("ERROR: could not connect to database to reset gate.")
        return
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE student_list_2024
                SET last_contest_poll_at = NULL
                WHERE discord_user_id = ANY(%s)
                """,
                (discord_user_ids,),
            )
        conn.commit()
    except Exception as e:
        # Column may not exist pre-migration; that's fine — gate degrades to
        # "always poll" anyway, so the backfill still works.
        print(f"(note) could not reset last_contest_poll_at: {e}")
        conn.rollback()
    finally:
        conn.close()


async def _run() -> int:
    args = _parse_args()
    user_ids = _target_user_ids(args.user)
    if not user_ids:
        print("No users to backfill.")
        return 1

    print(f"Backfilling {len(user_ids)} user(s)...")
    _reset_poll_gate(user_ids)

    total_new = 0
    total_badges = 0
    for uid in user_ids:
        try:
            new_contests, badges = await record_user_contests(uid)
        except Exception as e:
            print(f"  {uid}: ERROR {type(e).__name__}: {e}")
            continue
        total_new += len(new_contests)
        total_badges += len(badges)
        if new_contests or badges:
            names = ", ".join(c.contest_name for c in new_contests) or "—"
            badge_keys = ", ".join(b.get("key", "?") for b in badges) or "—"
            print(f"  {uid}: +{len(new_contests)} contest(s) [{names}]; badges: {badge_keys}")
        else:
            print(f"  {uid}: nothing new")

    print(f"\nDone. {total_new} new contest row(s), {total_badges} badge(s) awarded.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_run()))
