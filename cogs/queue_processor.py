"""
Queue Processor Cog — Background task that drains the submission queue.

Every 2 hours, checks if Codeforces/LeetCode APIs are back online (pulse
check, then processes any pending queued submissions. Posts results in the
watched channel and runs the full post-submit pipeline streaks, badges,
contests using the ORIGINAL submission timestamp.

Retry policy: 6 attempts × 2 hours = 12 hours max before marking as failed.
"""

import discord
from discord.ext import commands, tasks
import asyncio
import logging
from datetime import datetime, timezone

from config import WATCHED_CHANNEL_ID
from db.submission_queue import get_pending_jobs, mark_processed, mark_retry, mark_failed
from db.slash_commands_cp import process_slash_submission
from db.db import save_log, flag_late
from db.badges import check_and_award_milestones
from db.contests import record_user_contests
from utils.api_health import check_codeforces_pulse, check_leetcode_pulse
from utils.time_check import is_in_time_bracket
from utils.metrics import messages_sent_total

logger = logging.getLogger(__name__)


class QueueProcessorCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.process_queue.start()

    def cog_unload(self):
        self.process_queue.cancel()

    @tasks.loop(hours=2)
    async def process_queue(self):
        """Main queue drain loop — runs every 2 hours."""
        if not WATCHED_CHANNEL_ID:
            return

        # 1. Fetch pending jobs
        jobs = await asyncio.to_thread(get_pending_jobs)
        if not jobs:
            logger.debug("Queue processor: no pending jobs")
            return

        logger.info(f"Queue processor: found {len(jobs)} pending job(s)")

        # 2. Check API pulse once for the batch
        cf_alive = await asyncio.to_thread(check_codeforces_pulse)
        lc_alive = await asyncio.to_thread(check_leetcode_pulse)

        logger.info(f"Queue processor pulse: CF={'UP' if cf_alive else 'DOWN'}, LC={'UP' if lc_alive else 'DOWN'}")

        channel = self.bot.get_channel(WATCHED_CHANNEL_ID)
        if not channel:
            logger.warning(f"Queue processor: WATCHED_CHANNEL_ID {WATCHED_CHANNEL_ID} not found")
            return

        # 3. Process each job
        for job in jobs:
            job_id = job["id"]
            failed_platform = job["failed_platform"]
            retry_count = job["retry_count"]
            max_retries = job["max_retries"]

            # Skip if the failed platform is still down
            platform_ready = self._is_platform_ready(failed_platform, cf_alive, lc_alive)
            if not platform_ready:
                if retry_count + 1 >= max_retries:
                    # Max retries exhausted while platform still down
                    await asyncio.to_thread(
                        mark_failed, job_id,
                        f"Platform '{failed_platform}' still unreachable after {max_retries} attempts"
                    )
                    await self._post_failure(channel, job)
                else:
                    await asyncio.to_thread(mark_retry, job_id)
                    logger.info(
                        f"Queue job {job_id}: {failed_platform} still down, "
                        f"retry {retry_count + 1}/{max_retries}"
                    )
                continue

            # Platform is back! Try to process the submission
            try:
                cp_result = await asyncio.to_thread(
                    process_slash_submission, job["user_id"], job["day"]
                )
            except Exception as e:
                logger.error(f"Queue job {job_id}: process_slash_submission raised: {e}")
                if retry_count + 1 >= max_retries:
                    await asyncio.to_thread(mark_failed, job_id, str(e))
                    await self._post_failure(channel, job)
                else:
                    await asyncio.to_thread(mark_retry, job_id)
                continue

            # Check if it still returned a queue_required (API went down mid-request)
            if cp_result.get("queue_required"):
                if retry_count + 1 >= max_retries:
                    await asyncio.to_thread(
                        mark_failed, job_id,
                        cp_result.get("error_message", "API still failing")
                    )
                    await self._post_failure(channel, job)
                else:
                    await asyncio.to_thread(mark_retry, job_id)
                continue

            # Check for other errors
            if "error" in cp_result:
                # This is a user-level error (e.g., not registered), not transient
                await asyncio.to_thread(mark_failed, job_id, cp_result["error"])
                await self._post_failure(channel, job, reason=cp_result["error"])
                continue

            # ── Success! Run the full post-submit pipeline ──
            await asyncio.to_thread(mark_processed, job_id)

            # Use the ORIGINAL submitted_at timestamp for streaks and logs
            original_time = job["submitted_at"]

            # Time bracket check using original submission time
            is_legal_time = is_in_time_bracket(job["day"], original_time)
            if not is_legal_time:
                await asyncio.to_thread(flag_late, job["user_id"])

            # Save participation log with original timestamp
            await asyncio.to_thread(
                save_log,
                job["description"],
                job["discord_user_id"],
                0,  # no interaction.id for queued submissions
                original_time,
                1,
            )
            messages_sent_total.inc()

            # Milestone badges
            try:
                newly_awarded = await asyncio.to_thread(
                    check_and_award_milestones, job["discord_user_id"]
                )
            except Exception as e:
                logger.error(f"Queue job {job_id}: milestone check failed: {e}")
                newly_awarded = []

            # Contest detection
            try:
                new_contests, contest_badges = await record_user_contests(
                    job["discord_user_id"]
                )
            except Exception as e:
                logger.error(f"Queue job {job_id}: contest poll failed: {e}")
                new_contests, contest_badges = [], []

            # Post success in watched channel
            await self._post_success(channel, job, cp_result, is_legal_time)

            logger.info(f"Queue job {job_id}: processed successfully for user {job['user_id']} day {job['day']}")

    @process_queue.before_loop
    async def before_process_queue(self):
        await self.bot.wait_until_ready()

    @staticmethod
    def _is_platform_ready(failed_platform: str, cf_alive: bool, lc_alive: bool) -> bool:
        """Check if the platform(s) that failed are now back online."""
        if failed_platform == "both":
            return cf_alive and lc_alive
        elif failed_platform == "codeforces":
            return cf_alive
        elif failed_platform == "leetcode":
            return lc_alive
        return True  # unknown platform, try anyway

    async def _post_success(self, channel, job: dict, cp_result: dict, is_legal_time: bool):
        """Post a success embed in the watched channel for a dequeued submission."""
        solved = cp_result.get("solved_questions", [])
        total = cp_result.get("total_questions", 0)
        day = job["day"]

        color = discord.Color.green() if len(solved) == total else (
            discord.Color.gold() if len(solved) > 0 else discord.Color.red()
        )

        embed = discord.Embed(
            title=f"✅ Queued Submission Verified — Day {day}",
            description=(
                f"<@{job['discord_user_id']}>'s queued submission for **Day {day}** "
                f"has been successfully verified!\n\n"
                f"**Progress:** {len(solved)}/{total} Questions Solved"
            ),
            color=color,
        )
        embed.add_field(name="Student ID", value=job["user_id"], inline=True)

        if job["description"]:
            embed.add_field(name="Today's Work", value=job["description"], inline=False)

        if not is_legal_time:
            embed.add_field(
                name="⚠️ Late Submission",
                value="This submission was made outside the designated time window and has been marked as late.",
                inline=False,
            )

        embed.set_footer(text="Processed from submission queue")

        try:
            await channel.send(
                content=f"<@{job['discord_user_id']}>",
                embed=embed,
            )
        except discord.DiscordException as e:
            logger.error(f"Failed to post queue success embed: {e}")

    async def _post_failure(self, channel, job: dict, reason: str | None = None):
        """Post a failure embed in the watched channel for a dead-lettered submission."""
        day = job["day"]
        max_retries = job["max_retries"]

        embed = discord.Embed(
            title=f"❌ Queued Submission Failed — Day {day}",
            description=(
                f"<@{job['discord_user_id']}>'s queued submission for **Day {day}** "
                f"could not be verified after **{max_retries} attempts** (12 hours).\n\n"
                f"Please try `/submit` again manually."
            ),
            color=discord.Color.red(),
        )
        embed.add_field(name="Student ID", value=job["user_id"], inline=True)

        if reason:
            embed.add_field(name="Reason", value=reason[:1024], inline=False)

        embed.set_footer(text="Submission removed from queue")

        try:
            await channel.send(
                content=f"<@{job['discord_user_id']}>",
                embed=embed,
            )
        except discord.DiscordException as e:
            logger.error(f"Failed to post queue failure embed: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(QueueProcessorCog(bot))
