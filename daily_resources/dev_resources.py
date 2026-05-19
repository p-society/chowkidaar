import json
import datetime
import pytz
import discord
from discord.ext import tasks
import logging as logger

from daily_resources.daily_questions import get_current_day

# Load development resources from JSON
def load_dev_resources():
    try:
        with open("configs/dev.json", "r") as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Error loading dev.json: {e}", extra={"tags": {"event": "load_dev_resources"}})
        return {}

def load_event_config():
    try:
        with open("configs/event_config.json", "r") as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Error loading event_config.json: {e}", extra={"tags": {"event": "load_event_config"}})
        # Fallback config
        return {"dev": {"announcement_intro": "**Day {day} Development Resources** 📚\n\nToday's learning materials:\n\n", "announcement_outro": "\nExpand your knowledge with these resources. Happy learning! 🧠"}}

# Create development resources embed
def create_dev_resources_embed(day_number, resources_list, config):
    intro = config["dev"]["announcement_intro"].format(day=day_number)
    
    res_text = ""
    for i, resource in enumerate(resources_list, 1):
        resource_type = resource["type"]
        title = resource["title"]
        link = resource["link"]
        
        # Add emoji based on resource type
        if resource_type == "youtube":
            emoji = "🎥"
        elif resource_type == "blog":
            emoji = "📝"
        elif resource_type == "github":
            emoji = "💻"
        elif resource_type == "article":
            emoji = "📰"
        else:
            emoji = "🔗"
        
        res_text += f"{i}. {emoji} [{title}]({link})\n"
    
    outro = config["dev"]["announcement_outro"].format(day=day_number)
    
    embed = discord.Embed(
        title=f"📚 Learning Materials: Day {day_number}",
        description=f"{intro}\n{res_text}\n{outro}",
        color=discord.Color.blue()
    )
    
    branding = config.get("branding") or {}
    footer_text = branding.get("subtitle", "25 Days of Productivity")
    embed.set_footer(text=footer_text)
    
    return embed
        
class DevResourcesScheduler:
    def __init__(self, bot, channel_id, start_date):
        self.bot = bot
        self.channel_id = int(channel_id)
        self.resources = load_dev_resources()
        self.config = load_event_config()
        self.start_date = start_date
        self.daily_resources_task.start()
    
    async def unpin_previous_messages(self, channel):
        try:
            # Get pinned messages
            pinned_messages = await channel.pins()
            bot_id = self.bot.user.id
            curr_day = get_current_day(self.start_date)
            for pinned in pinned_messages:
                if pinned.author.id != bot_id:
                    continue
                
                content = pinned.content or ""
                if pinned.embeds:
                    content += " " + (pinned.embeds[0].title or "") + " " + (pinned.embeds[0].description or "")
                
                if "Day " in content and not f"Day {curr_day}" in content:
                    await pinned.unpin()
                    logger.info(f"Unpinned old message: {pinned.id}", 
                              extra={"tags": {"event": "message_unpin"}})
        except Exception as e:
            logger.error(f"Error unpinning previous messages: {e}", 
                      extra={"tags": {"event": "unpin_error"}})
        
    def cog_unload(self):
        self.daily_resources_task.cancel()
    
    # This task runs every day at 6:15 AM IST (00:45 UTC)
    @tasks.loop(time=datetime.time(hour=1, minute=30, tzinfo=datetime.timezone.utc))
    async def daily_resources_task(self):
        try:
            # Calculate which day we're on
            today = datetime.datetime.now(datetime.timezone.utc).date()
            delta = (today - self.start_date).days + 1  # +1 because we want day 1, 2, 3, etc.
            day = delta if delta > 0 else 0
            
            # Check if we're within the resources window
            if 0 < day <= len(self.resources):
                day_str = str(day)
                if day_str in self.resources:
                    channel = self.bot.get_channel(self.channel_id)
                    if channel:
                        resources_list = self.resources[day_str]
                        embed = create_dev_resources_embed(day, resources_list, self.config)
                        sent_message = await channel.send(embed=embed)
                    try:
                        await self.unpin_previous_messages(channel)    
                        await sent_message.pin()
                        logger.info(f"Sent day {day} dev resources to channel", 
                                  extra={"tags": {"event": "daily_resources"}})
                    except Exception as pin_error:
                        logger.error(f"Failed to pin message for day {day}: {pin_error}", 
                                  extra={"tags": {"event": "daily_resources"}})
                    else:
                        logger.error(f"Channel {self.channel_id} not found", 
                                  extra={"tags": {"event": "daily_resources"}})
                else:
                    logger.error(f"No dev resources found for day {day}", 
                              extra={"tags": {"event": "daily_resources"}})
        except Exception as e:
            logger.error(f"Error in daily dev resources task: {e}", 
                      extra={"tags": {"event": "daily_resources"}})
    
    # Wait until bot is ready to start the task
    @daily_resources_task.before_loop
    async def before_daily_resources_task(self):
        await self.bot.wait_until_ready()
        logger.info(f"Dev resources scheduler initialized. Will send at 6:15 AM IST.", 
                  extra={"tags": {"event": "scheduler_init"}})