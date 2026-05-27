import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
import asyncio
from datetime import datetime, timezone, timedelta

from config import WATCHED_CHANNEL_ID, CONTEST_ROLE_ID
from integrations.upcoming_contests import fetch_all_upcoming_contests
from db.contest_reminders import mark_sent, was_sent
from utils.permissions import is_watched_channel
from utils.event_window import get_event_window

logger = logging.getLogger(__name__)

# Reminder offsets and their tolerance windows. Each entry: (label, target,
# half_window). We fire when `target - half_window ≤ time_left ≤ target +
# half_window`. The reminder loop ticks every 5 min, so windows must be ≥
# 5 min wide to avoid missing a tick.
_REMINDER_WINDOWS = [
    ("12h", timedelta(hours=12),  timedelta(minutes=30)),
    ("15m", timedelta(minutes=15), timedelta(minutes=5)),
    ("0m",  timedelta(minutes=0),  timedelta(minutes=5)),
]

# After this many consecutive clist.by failures, throttle the reminder loop.
# The clist.by API occasionally has transient outages; without this guard
# we'd hammer it every 5 min and spam the logs.
_FAILURE_THRESHOLD_FOR_BACKOFF = 3
# When throttled, skip this many subsequent loop iterations before retrying.
_BACKOFF_TICKS = 6  # 6 ticks × 5 min = 30 min cooldown


def _process_contest_reminders_tx(contests, now) -> list[tuple]:
    from db.db import connect_to_database
    from db.contest_reminders import was_sent, mark_sent
    conn = connect_to_database(purpose="Contest Reminders Dedup")
    if not conn:
        return []
    
    to_send = []
    try:
        for c in contests:
            time_left = c.start_time - now
            for label, target, half_window in _REMINDER_WINDOWS:
                lower, upper = target - half_window, target + half_window
                if not (lower <= time_left <= upper):
                    continue
                if mark_sent(c.url, label, conn=conn):
                    to_send.append((c, label))
        return to_send
    finally:
        conn.close()


class ContestsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Consecutive-failure tracking for backoff. We still consult the DB
        # dedup table (db.contest_reminders) for cross-restart correctness;
        # the counters below just keep us off clist.by's back during outages.
        self._consecutive_failures = 0
        self._ticks_to_skip = 0
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    @app_commands.command(name="upcoming", description="Show upcoming CP contests")
    @is_watched_channel()
    async def upcoming_command(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            contests = await fetch_all_upcoming_contests()
            now = datetime.now(timezone.utc)
            one_week = now + timedelta(days=7)

            weekly_contests = [c for c in contests if now <= c.start_time <= one_week]

            if not weekly_contests:
                await interaction.followup.send("No upcoming contests found in the next 1 week.")
                return

            embed = discord.Embed(
                title="📅 Upcoming contests in 1 week",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )

            for c in weekly_contests[:10]:  # show up to 10
                time_str = f"<t:{int(c.start_time.timestamp())}:F> (<t:{int(c.start_time.timestamp())}:R>)"
                duration_hrs = c.duration.total_seconds() / 3600.0
                desc = (
                    f"**Time:** {time_str}\n"
                    f"**Duration:** {duration_hrs:.1f} hrs\n"
                    f"**Link:** [Click Here]({c.url})"
                )
                embed.add_field(
                    name=f"[{c.platform}] {c.name}",
                    value=desc,
                    inline=False,
                )

            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error in upcoming_command: {e}")
            await interaction.followup.send("An error occurred while fetching upcoming contests.")

    @tasks.loop(minutes=5)
    async def reminder_loop(self):
        # ── 1. Skip iterations while we're in backoff after consecutive failures
        if self._ticks_to_skip > 0:
            self._ticks_to_skip -= 1
            return

        # ── 2. Don't run outside the event window. Reminders are an
        #    event-scoped feature; we don't want @CONTEST_ROLE pings to
        #    keep firing weeks after the event ends.
        now = datetime.now(timezone.utc)
        try:
            start, end = get_event_window()
        except Exception as e:
            logger.error(f"reminder_loop: event_window unreadable: {e}")
            return
        if now < start or now >= end:
            return

        # ── 3. Fetch upcoming contests, with failure-counted backoff.
        try:
            contests = await fetch_all_upcoming_contests()
        except Exception as e:
            self._consecutive_failures += 1
            logger.error(
                f"reminder_loop fetch failed "
                f"(consecutive={self._consecutive_failures}): {e}"
            )
            if self._consecutive_failures >= _FAILURE_THRESHOLD_FOR_BACKOFF:
                logger.warning(
                    f"reminder_loop: backing off for {_BACKOFF_TICKS} ticks "
                    f"after {self._consecutive_failures} consecutive failures."
                )
                self._ticks_to_skip = _BACKOFF_TICKS
                self._consecutive_failures = 0
            return
        # Successful fetch — reset the counter.
        self._consecutive_failures = 0

        channel = self.bot.get_channel(WATCHED_CHANNEL_ID)
        if not channel:
            logger.warning(f"reminder_loop: WATCHED_CHANNEL_ID {WATCHED_CHANNEL_ID} not found")
            return

        # ── 4. For each upcoming contest, fire any matching reminder windows.
        #    All DB checks are offloaded and consolidated to save resources!
        reminders_to_send = await asyncio.to_thread(_process_contest_reminders_tx, contests, now)

        for c, label in reminders_to_send:
            title, mention_role = _reminder_copy(label)
            try:
                await self.send_reminder(channel, c, title, mention_role=mention_role)
            except Exception as e:
                logger.error(f"reminder send failed for {c.url} [{label}]: {e}")

    @reminder_loop.before_loop
    async def before_reminder_loop(self):
        await self.bot.wait_until_ready()

    async def send_reminder(self, channel, contest, title_msg, mention_role):
        embed = discord.Embed(
            title=title_msg,
            description=f"**[{contest.platform}] {contest.name}**",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow(),
        )
        time_str = f"<t:{int(contest.start_time.timestamp())}:F> (<t:{int(contest.start_time.timestamp())}:R>)"
        embed.add_field(name="Start Time", value=time_str, inline=False)
        embed.add_field(name="Duration", value=f"{contest.duration.total_seconds() / 3600.0:.1f} hours", inline=False)
        embed.add_field(name="Link", value=f"[Go to Contest]({contest.url})", inline=False)
        embed.set_footer(text="React with ✋ if you are participating!")

        content = ""
        if mention_role and CONTEST_ROLE_ID:
            content = f"<@&{CONTEST_ROLE_ID}>"

        message = await channel.send(content=content, embed=embed)
        try:
            await message.add_reaction("✋")
        except discord.Forbidden:
            logger.warning("Bot does not have permission to add reactions.")


def _reminder_copy(label: str) -> tuple[str, bool]:
    """(title, mention_role) for a given reminder window label."""
    if label == "12h":
        return ("🔔 Contest in 12 Hours! Register now!", True)
    if label == "15m":
        return ("🚨 Contest starting in 15 Minutes!", True)
    # 0m or anything else: no @role ping; the previous notifications already
    # nudged everyone, this is just a "live now" marker.
    return ("🚀 Contest has Started!", False)


async def setup(bot: commands.Bot):
    await bot.add_cog(ContestsCog(bot))
