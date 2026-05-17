from os import times
import discord
from discord import app_commands
from config import DISCORD_TOKEN, WATCHED_CHANNEL_ID
from discord.ext import commands
from db.db import save_log, update_log, delete_log, flag_late, register_user, delete_cp_log
from utils.time_check import can_send_message, is_in_time_bracket
from prometheus_client import Counter , Gauge, start_http_server
import logging as logger
from db.slash_commands_cp import process_slash_submission, get_user_status
from daily_resources.daily_questions import DailyQuestionScheduler, get_start_date  # Add this import
from daily_resources.dev_resources import DevResourcesScheduler  
from datetime import datetime

intents = discord.Intents.default()
intents.messages = True  # Ensure the bot can read messages
intents.message_content = True  # Add this line if you need access to message content
bot = commands.Bot(command_prefix="!", intents=intents)
bot.activity = discord.Activity(type=discord.ActivityType.watching, name="for message updates")

message_new_attempts_total= Counter('discord_messages_new_attempts_total', 'Total number of new messages received')
message_new_edits_total= Counter('discord_messages_new_edit_attempts_total', 'Total number of patch request received')

messages_sent_total = Counter('discord_messages_sent_total', 'Total number of messages saved in DB')
messages_edited_total = Counter('discord_messages_edited_total', 'Total number of messages patched in DB')
messages_deleted_total = Counter('discord_messages_deleted_total', 'Total number of messages deleted in DB')

errors_encountered_total = Counter('errors_encountered_total','Total Errors Encountered during bot"s processing of messages')

start_http_server(8000) 

def is_watched_channel():
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.channel_id == WATCHED_CHANNEL_ID
    return app_commands.check(predicate)

@bot.tree.command(name="register", description="Register your CP handles")
@is_watched_channel()
async def register(interaction: discord.Interaction, student_id: str, name: str, leetcode_handle: str, codeforces_handle: str):
    success = register_user(student_id, name, leetcode_handle, codeforces_handle)
    
    embed = discord.Embed(title="Registration Status", color=discord.Color.green() if success else discord.Color.red())
    if success:
        embed.description = "✅ User registered successfully!"
        embed.add_field(name="Name", value=name, inline=True)
        embed.add_field(name="Student ID", value=student_id, inline=True)
        embed.add_field(name="LeetCode", value=leetcode_handle, inline=True)
        embed.add_field(name="CodeForces", value=codeforces_handle, inline=True)
    else:
        embed.description = "❌ Failed to register user. Please try again or contact an admin."
        
    await interaction.response.send_message(embed=embed)

def create_submission_embed(user_id, name, day, description, cp_result):
    if "error" in cp_result:
        embed = discord.Embed(title=f"Day {day} Submission Error", color=discord.Color.red())
        embed.description = f"❌ {cp_result['error']}"
        return embed
        
    solved = cp_result['solved_questions']
    total = cp_result['total_questions']
    day_questions = cp_result['day_questions']
    
    color = discord.Color.green() if len(solved) == total else (discord.Color.gold() if len(solved) > 0 else discord.Color.red())
    
    embed = discord.Embed(title=f"Day {day} Submission: {name}", color=color)
    embed.add_field(name="Student ID", value=user_id, inline=True)
    embed.add_field(name="Progress", value=f"{len(solved)}/{total} Questions Solved", inline=True)
    
    questions_status = ""
    for q in day_questions:
        if q.startswith("LC"): q_id = q[3:]
        elif q.startswith("CF"): q_id = q[3:]
        else: q_id = q
        status_emoji = "✅" if q_id in solved else "❌"
        questions_status += f"{status_emoji} {q}\n"
    
    embed.add_field(name="Questions", value=questions_status, inline=False)
    
    if description:
        embed.add_field(name="Today's Work", value=description, inline=False)
        
    return embed

@bot.tree.command(name="submit", description="Submit your daily CP progress")
@is_watched_channel()
async def submit(interaction: discord.Interaction, student_id: str, day: int, description: str):
    await interaction.response.defer()
    
    # Process CP submissions
    cp_result = process_slash_submission(student_id, day)
    
    if "error" not in cp_result:
        # Time bracket check
        is_legal_time = is_in_time_bracket(day, datetime.now(datetime.UTC))
        if not is_legal_time:
            flag_late(student_id)
            
        # Save log
        save_log(description, interaction.user.id, interaction.id, interaction.created_at, 1)
        messages_sent_total.inc()
        
    embed = create_submission_embed(student_id, cp_result.get('name', 'User'), day, description, cp_result)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="edit_submission", description="Edit a previous daily CP progress submission")
@is_watched_channel()
async def edit_submission(interaction: discord.Interaction, student_id: str, day: int, new_description: str):
    await interaction.response.defer()
    
    cp_result = process_slash_submission(student_id, day)
    
    if "error" not in cp_result:
        update_log(interaction.id, new_description, 1, datetime.now(datetime.UTC))
        messages_edited_total.inc()
        
    embed = create_submission_embed(student_id, cp_result.get('name', 'User'), day, new_description, cp_result)
    embed.title = f"📝 Edited " + embed.title
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="delete_submission", description="Delete a previous daily CP progress submission")
@is_watched_channel()
async def delete_submission(interaction: discord.Interaction, student_id: str, day: int):
    await interaction.response.defer()
    
    delete_cp_log(student_id, day)
    
    embed = discord.Embed(title=f"Day {day} Submission Deleted", color=discord.Color.red())
    embed.description = f"🗑️ The submission for Day {day} has been removed for student {student_id}."
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="status", description="Check your CP progress status for a specific day")
@is_watched_channel()
async def status(interaction: discord.Interaction, student_id: str, day: int):
    await interaction.response.defer()
    
    status_result = get_user_status(student_id, day)
    
    if "error" in status_result:
        embed = discord.Embed(title=f"Day {day} Status Error", color=discord.Color.red())
        embed.description = f"❌ {status_result['error']}"
        await interaction.followup.send(embed=embed)
        return
        
    solved = status_result['solved_questions']
    total = status_result['total_questions']
    day_questions = status_result['day_questions']
    
    color = discord.Color.green() if len(solved) == total else (discord.Color.gold() if len(solved) > 0 else discord.Color.red())
    
    embed = discord.Embed(title=f"Day {day} Status", color=color)
    embed.add_field(name="Student ID", value=student_id, inline=True)
    embed.add_field(name="Progress", value=f"{len(solved)}/{total} Questions Solved", inline=True)
    
    questions_status = ""
    for q in day_questions:
        if q.startswith("LC"): q_id = q[3:]
        elif q.startswith("CF"): q_id = q[3:]
        else: q_id = q
        status_emoji = "✅" if q_id in solved else "❌"
        questions_status += f"{status_emoji} {q}\n"
    
    embed.add_field(name="Questions", value=questions_status, inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="help", description="List all available commands")
@is_watched_channel()
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="Chowkidaar Bot Commands", color=discord.Color.blue())
    embed.description = "Here are all the available slash commands:"
    
    embed.add_field(name="📝 `/register`", value="Register your CP handles. \n`student_id`, `name`, `leetcode`, `codeforces`", inline=False)
    embed.add_field(name="🚀 `/submit`", value="Submit your daily CP progress. \n`student_id`, `day`, `description`", inline=False)
    embed.add_field(name="✏️ `/edit_submission`", value="Edit a previous daily CP progress submission. \n`student_id`, `day`, `new_description`", inline=False)
    embed.add_field(name="🗑️ `/delete_submission`", value="Delete a previous daily CP progress submission. \n`student_id`, `day`", inline=False)
    embed.add_field(name="📊 `/status`", value="Check your CP progress status for a specific day. \n`student_id`, `day`", inline=False)
    embed.add_field(name="❓ `/help`", value="List all available commands.", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("❌ This command can only be used in the designated progress channel.", ephemeral=True)
    else:
        logger.error(f"App command error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)


@bot.event
async def on_message(message):
    message_new_attempts_total.inc()
    if message.author == bot.user:
        return

    # No text processing is required anymore for CP tracking; everything is handled via slash commands.
    # If other traditional commands exist, they would be processed here.
    await bot.process_commands(message)

@bot.event
async def on_ready():
    logger.info(f"Bot is ready. Logged in as {bot.user}", extra={"tags": {"event": "on_ready"}})
    print(f"Bot is ready. Logged in as {bot.user}")
    
    # Start the daily question scheduler
    start_date = get_start_date()  # Import this from daily_questions
    question_scheduler = DailyQuestionScheduler(bot, WATCHED_CHANNEL_ID)
    dev_resources_scheduler = DevResourcesScheduler(bot, WATCHED_CHANNEL_ID, start_date)
    
    logger.info("Daily schedulers started", extra={"tags": {"event": "scheduler_start"}})
    
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} command(s)")
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
        print(f"Failed to sync commands: {e}")
    
bot.run(DISCORD_TOKEN)
