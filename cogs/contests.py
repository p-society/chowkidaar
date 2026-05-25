import discord
from discord.ext import commands, tasks
from discord import app_commands
import logging
from datetime import datetime, timezone, timedelta
from typing import Set, Tuple
from config import WATCHED_CHANNEL_ID, CONTEST_ROLE_ID
from integrations.upcoming_contests import fetch_all_upcoming_contests

logger = logging.getLogger(__name__)

class ContestsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Format of set elements: (contest_url, reminder_type)
        # reminder_type can be '12h', '15m', '0m'
        self.notified: Set[Tuple[str, str]] = set()
        self.reminder_loop.start()

    def cog_unload(self):
        self.reminder_loop.cancel()

    @app_commands.command(name="upcoming", description="Show upcoming CP contests")
    async def upcoming_command(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            contests = await fetch_all_upcoming_contests()
            now = datetime.now(timezone.utc)
            one_week = now + timedelta(days=7)
            
            # Filter contests within the next 1 week
            weekly_contests = [c for c in contests if now <= c.start_time <= one_week]
            
            if not weekly_contests:
                await interaction.followup.send("No upcoming contests found in the next 1 week.")
                return

            embed = discord.Embed(
                title="📅 Upcoming contests in 1 week", 
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            
            for c in weekly_contests[:10]: # show up to 10
                time_str = f"<t:{int(c.start_time.timestamp())}:F> (<t:{int(c.start_time.timestamp())}:R>)"
                duration_hrs = c.duration.total_seconds() / 3600.0
                desc = f"**Time:** {time_str}\n**Duration:** {duration_hrs:.1f} hrs\n**Link:** [Click Here]({c.url})"
                embed.add_field(
                    name=f"[{c.platform}] {c.name}",
                    value=desc,
                    inline=False
                )
            
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"Error in upcoming_command: {e}")
            await interaction.followup.send("An error occurred while fetching upcoming contests.")

    @tasks.loop(minutes=5)
    async def reminder_loop(self):
        try:
            contests = await fetch_all_upcoming_contests()
            now = datetime.now(timezone.utc)
            
            channel = self.bot.get_channel(WATCHED_CHANNEL_ID)
            if not channel:
                logger.warning(f"Could not find WATCHED_CHANNEL_ID: {WATCHED_CHANNEL_ID}")
                return

            for c in contests:
                time_left = c.start_time - now
                
                # Check 12 hours window (11.5 to 12.5 hours)
                if timedelta(hours=11, minutes=30) <= time_left <= timedelta(hours=12, minutes=30):
                    if (c.url, '12h') not in self.notified:
                        await self.send_reminder(channel, c, "🔔 Contest in 12 Hours! Register now!", mention_role=True)
                        self.notified.add((c.url, '12h'))
                        
                # Check 15 mins window (10 to 20 mins)
                elif timedelta(minutes=10) <= time_left <= timedelta(minutes=20):
                    if (c.url, '15m') not in self.notified:
                        await self.send_reminder(channel, c, "🚨 Contest starting in 15 Minutes!", mention_role=True)
                        self.notified.add((c.url, '15m'))
                        
                # Check 0 mins window (-5 to 5 mins)
                elif timedelta(minutes=-5) <= time_left <= timedelta(minutes=5):
                    if (c.url, '0m') not in self.notified:
                        await self.send_reminder(channel, c, "🚀 Contest has Started!", mention_role=False)
                        self.notified.add((c.url, '0m'))
                        
        except Exception as e:
            logger.error(f"Error in contest reminder_loop: {e}")

    @reminder_loop.before_loop
    async def before_reminder_loop(self):
        await self.bot.wait_until_ready()

    async def send_reminder(self, channel, contest, title_msg, mention_role):
        embed = discord.Embed(
            title=title_msg,
            description=f"**[{contest.platform}] {contest.name}**",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
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

async def setup(bot: commands.Bot):
    await bot.add_cog(ContestsCog(bot))
