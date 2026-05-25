import discord
from discord.ext import commands
from config import DISCORD_TOKEN, WATCHED_CHANNEL_ID
from utils.metrics import start_metrics_server, message_new_attempts_total
from daily_resources.daily_questions import DailyQuestionScheduler, get_start_date
from daily_resources.dev_resources import DevResourcesScheduler
import logging as logger

class ChowkidaarBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.messages = True
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.activity = discord.Activity(type=discord.ActivityType.watching, name="for message updates")

    async def setup_hook(self):
        # Load Cogs
        await self.load_extension("cogs.registration")
        await self.load_extension("cogs.submissions")
        await self.load_extension("cogs.badges")
        await self.load_extension("cogs.help")
        await self.load_extension("cogs.contests")

        # Auto-synchronize badges config to the database
        try:
            from db.badges_config import sync_badges_to_db
            sync_badges_to_db()
        except Exception as e:
            logger.error(f"Failed to auto-sync badges on startup: {e}")

        # Sync commands
        try:
            from os import getenv
            dev_guild_id = getenv("DEV_GUILD_ID")
            if dev_guild_id:
                guild = discord.Object(id=int(dev_guild_id))
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                print(f"Synced {len(synced)} command(s) to guild {dev_guild_id} (instant)")
                logger.info(f"Synced {len(synced)} command(s) to guild {dev_guild_id}")
                self.tree.clear_commands(guild=None)
                await self.tree.sync()
                print("Cleared global commands (so they don't duplicate the guild copies)")
            else:
                synced = await self.tree.sync()
                print(f"Synced {len(synced)} command(s) globally (may take up to 1h)")
                logger.info(f"Synced {len(synced)} command(s) globally")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
            print(f"Failed to sync commands: {e}")

bot = ChowkidaarBot()

@bot.event
async def on_message(message):
    message_new_attempts_total.inc()
    if message.author == bot.user:
        return
    await bot.process_commands(message)

@bot.event
async def on_ready():
    logger.info(f"Bot is ready. Logged in as {bot.user}", extra={"tags": {"event": "on_ready"}})
    print(f"Bot is ready. Logged in as {bot.user}")
    
    # Start the daily question scheduler
    start_date = get_start_date()
    DailyQuestionScheduler(bot, WATCHED_CHANNEL_ID)
    DevResourcesScheduler(bot, WATCHED_CHANNEL_ID, start_date)
    
    logger.info("Daily schedulers started", extra={"tags": {"event": "scheduler_start"}})

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.CheckFailure):
        await interaction.response.send_message("❌ This command can only be used in the designated progress channel.", ephemeral=True)
    else:
        logger.error(f"App command error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)

if __name__ == "__main__":
    # Start Prometheus server
    start_metrics_server(8000)
    # Run the bot
    bot.run(DISCORD_TOKEN)
