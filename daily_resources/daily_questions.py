import discord
import json
import asyncio
import datetime
import pytz
import os
from discord.ext import tasks
import logging as logger

# Load questions from JSON
def load_questions():
    try:
        with open("db/questions.json", "r") as file:
            return json.load(file)
    except Exception as e:
        logger.error(f"Error loading questions.json: {e}", extra={"tags": {"event": "load_questions"}})
        return {}

# Format URLs for questions
def format_question_links(day_number, questions_list):
    formatted_links = []
    
    for question in questions_list:
        if question.startswith("LC-"):
            # LeetCode question
            slug = question[3:]  # Remove "LC-" prefix
            url = f"https://leetcode.com/problems/{slug}"
            formatted_links.append(f"LeetCode: [{slug}]({url})")
        elif question.startswith("CF-"):
            # CodeForces question
            problem_id = question[3:]  # Remove "CF-" prefix
            url = f"https://codeforces.com/problemset/problem/{problem_id[:-1]}/{problem_id[-1]}"
            formatted_links.append(f"CodeForces: [{problem_id}]({url})")
    
    return formatted_links

# Create daily question message
def create_daily_question_message(day_number, questions_list):
    links = format_question_links(day_number, questions_list)
    
    message = f"**Day {day_number} Coding Challenge** 🚀\n\n"
    message += "Today's questions:\n\n"
    
    for i, link in enumerate(links, 1):
        message += f"{i}. {link}\n"
    
    message += "\nRemember to submit your solutions in this channel by end of day! Good luck! 💪"
    print(f"Created message for day {day_number}: {message}")
    return message

# Calculate days since start date
def get_current_day(start_date):
    today = datetime.datetime.now(datetime.timezone.utc).date()
    delta = (today - start_date).days + 1  # +1 because we want day 1, 2, 3, etc.
    return delta if delta > 0 else 0

# Get the first day of next month
def get_start_date():
    return datetime.datetime(2025, 6, 1, tzinfo=datetime.timezone.utc).date()


class DailyQuestionScheduler:
    def __init__(self, bot, channel_id):
        self.bot = bot
        self.channel_id = int(channel_id)
        self.questions = load_questions()
        self.start_date = get_start_date()
        self.daily_task.start()
        
    def cog_unload(self):
        self.daily_task.cancel()
    
    # This task runs every day at specified time
    @tasks.loop(time=datetime.time(hour=1, minute=30, tzinfo=datetime.timezone.utc))
    async def daily_task(self):
        try:
            day = get_current_day(self.start_date)
            
            # Check if we're within the 25-day window
            if 0 < day <= 25:
                day_str = str(day)
                if day_str in self.questions:
                    channel = self.bot.get_channel(self.channel_id)
                    if channel:
                        questions_list = self.questions[day_str]
                        message = create_daily_question_message(day, questions_list)
                        cp_message = await channel.send(message)
                    try:
                        await cp_message.pin()
                        logger.info(f"Sent day {day} dev questions to channel", 
                                  extra={"tags": {"event": "daily_resources"}})
                    except Exception as pin_error:
                        logger.error(f"Failed to pin message for day {day}: {pin_error}", 
                                  extra={"tags": {"event": "daily_resources"}})
                    else:
                        logger.error(f"Channel {self.channel_id} not found", 
                                   extra={"tags": {"event": "daily_question"}})
                else:
                    logger.error(f"No questions found for day {day}", 
                               extra={"tags": {"event": "daily_question"}})
        except Exception as e:
            logger.error(f"Error in daily question task: {e}", 
                       extra={"tags": {"event": "daily_question"}})
    
    # Wait until 6AM to start the task
    @daily_task.before_loop
    async def before_daily_task(self):
        await self.bot.wait_until_ready()
        logger.info(f"Daily question scheduler initialized. Starting date: {self.start_date}", 
                  extra={"tags": {"event": "scheduler_init"}})