import json
import datetime
import pytz
from discord.ext import tasks
import logging as logger

from daily_resources.daily_questions import get_current_day

# Load development resources from JSON
def load_dev_resources():
    try:
        with open("db/dev.json", "r") as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Error loading dev.json: {e}", extra={"tags": {"event": "load_dev_resources"}})
        return {}

# Create development resources message
def create_dev_resources_message(day_number, resources_list):
    message = f"**Day {day_number} Development Resources** 📚\n\n"
    message += "Today's learning materials:\n\n"
    
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
        
        message += f"{i}. {emoji} [{title}]({link})\n"
    
    message += "\nExpand your knowledge with these resources. Happy learning! 🧠"
    print(f"Created dev resources message for day {day_number}")
    return message
        
class DevResourcesScheduler:
    def __init__(self, bot, channel_id, start_date):
        self.bot = bot
        self.channel_id = int(channel_id)
        self.resources = load_dev_resources()
        self.start_date = start_date
        self.daily_resources_task.start()
    
    async def unpin_previous_messages(self, channel):
        try:
            # Get pinned messages
            pinned_messages = await channel.pins()
            # Look for messages from our bot that match our format
            bot_id = self.bot.user.id
            for pinned in pinned_messages:
                # Check if message is from our bot and from a previous day
                if (pinned.author.id == bot_id and 
                    ("Day " in pinned.content) and 
                    not f"Day {get_current_day(self.start_date)}" in pinned.content):
                    await pinned.unpin()
                    logger.info(f"Unpinned old message: {pinned.content[:30]}...", 
                              extra={"tags": {"event": "message_unpin"}})
        except Exception as e:
            logger.error(f"Error unpinning previous messages: {e}", 
                      extra={"tags": {"event": "unpin_error"}})
        
    def cog_unload(self):
        self.daily_resources_task.cancel()
    
    # This task runs every day at 6:15 AM IST (00:45 UTC)
    @tasks.loop(time=datetime.time(hour=1, minute=23, tzinfo=datetime.timezone.utc))
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
                        message = create_dev_resources_message(day, resources_list)
                        sent_message = await channel.send(message, suppress_embeds=True)
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