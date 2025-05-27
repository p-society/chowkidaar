from os import times
import discord
from config import DISCORD_TOKEN, WATCHED_CHANNEL_ID
from discord.ext import commands
from db.db import save_log, check_intext_validity, update_log, delete_log, flag_late
from utils.time_check import can_send_message, is_in_time_bracket
from prometheus_client import Counter , Gauge, start_http_server
import logging as logger
from db.mark_cp_logs import process_submissions  # Add CP processing import

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

@bot.event
async def on_ready(): 
    logger.info(f"Bot is ready. Logged in as {bot.user}",extra={"tags": {"event": "on_ready"}})
    print(f"Bot is ready. Logged in as {bot.user}")

@bot.event
async def on_message(message):
    message_new_attempts_total.inc()
    if message.author == bot.user:
        return

    if message.channel.id != WATCHED_CHANNEL_ID:
        return
    
    # ignore arcane
    if message.author.id == 437808476106784770:
        return

    discord_user_id = message.author.id
    discord_message_id = message.id
    content = str(message.content)
    timestamp = message.created_at
    logger.info(f"Received Message from discord_user_id {discord_user_id}",extra={"tags": {"event": "on_message"}})


    try:
        # Process CP submissions
        cp_result = process_submissions(content)
        
        # Handle registration message
        if cp_result and "status" in cp_result and cp_result["status"] == "success" and "message" in cp_result and "registered" in cp_result["message"].lower():
            logger.info(f"User registration successful for {discord_user_id}.")
            logger.info(f"Added 📝 reaction for successful registration")
            await message.add_reaction("📝")
            
            # Save registration message to database without validity check
            save_log(
                content,
                discord_user_id,
                discord_message_id,
                timestamp,
                1,
            )
            logger.info(f"Registration message from {message.author.name} saved to the database.",extra={"tags": {"event": "on_message"}})
            await message.add_reaction("✔")
            messages_sent_total.inc()
        
        # Handle daily log message
        if cp_result and "status" in cp_result and cp_result["status"] == "success" :
            is_legal_time = is_in_time_bracket(cp_result['day'], timestamp)
            in_text_valid = check_intext_validity(content)
            daily_goal_status = len(cp_result['solved_questions'])/(cp_result['total_questions'])
            
            if daily_goal_status == 1:
                logger.info(f"CP submissions processed successfully for user {discord_user_id}.", extra={"tags": {"event": "on_message"}})
                logger.info(f"{discord_user_id} has completed all the questions", extra={"tags": {"event": "on_message"}})
                await message.add_reaction("✅")
                logger.info(f"Added ✅ reaction", extra={"tags": {"event": "on_message"}})
            elif daily_goal_status < 1 and daily_goal_status != 0:
                logger.info(f"CP submissions processed successfully for user {discord_user_id}.", extra={"tags": {"event": "on_message"}})
                logger.info(f"{discord_user_id} has partially completed the questions", extra={"tags": {"event": "on_message"}})
                await message.add_reaction("⏳")
                logger.info(f"Added ⏳ reaction", extra={"tags": {"event": "on_message"}})
            elif daily_goal_status == 0:
                logger.info(f"No CP submissions for user {discord_user_id}.", extra={"tags": {"event": "on_message"}})
                logger.info(f"{discord_user_id} has no submissions", extra={"tags": {"event": "on_message"}})
                await message.add_reaction("❌")
                logger.info(f"Added ❌ reaction", extra={"tags": {"event": "on_message"}})

            if not is_legal_time:
                flag_late(cp_result['user_id'])
                logger.info(f"CP submissions processed with late submission for user {discord_user_id}.", extra={"tags": {"event": "on_message"}})
                await message.add_reaction("⏰")
                logger.info(f"Added ⏰ reaction", extra={"tags": {"event": "on_message"}})


            # Check message validity and save to database only for daily logs
            if can_send_message(discord_user_id, timestamp, cp_result['day']):
                logger.info(f"discord_message_id :{discord_message_id} can be stored in DB.",extra={"tags": {"event": "on_message"}})
                save_log(
                    content,
                    discord_user_id,
                    discord_message_id,
                    timestamp,
                    in_text_valid,
                )
                logger.info(f"Message from {message.author.name} saved to the database.",extra={"tags": {"event": "on_message"}})
                print(f"Message from {message.author.name} saved to the database.")
                await message.add_reaction("🎊")
                logger.info(f"Reaction 🎊 added to discord_user_id: {discord_user_id} for message id:{ discord_message_id}  successfully.",extra={"tags": {"event": "on_message"}})
                messages_sent_total.inc()   
            else:
                logger.warning(f"Message from {message.author.name} could not be saved to the database.",extra={"tags": {"event": "on_message"}})
                print(f"Message from {message.author.name} could not be saved to the database.")
                await message.add_reaction("👁️")
                logger.info(f"Reaction 👁️ added to discord_user_id: {discord_user_id} for message id:{ discord_message_id}  successfully.",extra={"tags": {"event": "on_message"}})
        
        # Handle errors
        elif cp_result and "error" in cp_result:
            error_msg = cp_result['error']
            logger.warning(f"CP processing error: {error_msg}", extra={"tags": {"event": "on_message"}})
            
            # Different reactions for different types of errors
            if "not registered" in error_msg.lower() or "handle not found" in error_msg.lower():
                await message.add_reaction("📝")  # Registration needed
                logger.info(f"Added 📝 reaction for registration needed", extra={"tags": {"event": "on_message"}})
            else:
                await message.add_reaction("⚠️")  # Other errors
                logger.info(f"Added ⚠️ reaction for other errors", extra={"tags": {"event": "on_message"}})


    except Exception as e:
        logger.error(f"Error processing message: {e}",extra={"tags": {"event": "on_message"}})
        print(f"Error processing message: {e}")
        errors_encountered_total.inc()
    await bot.process_commands(message)
    
@bot.event
async def on_message_edit(old_message, new_message):
    message_new_edits_total.inc()
    if new_message.author == bot.user:
        return
    if new_message.channel.id != WATCHED_CHANNEL_ID:
        return
    # ignore arcane
    if new_message.author.id == 437808476106784770:
        return
    discord_user_id = new_message.author.id
    discord_message_id = new_message.id
    content = str(new_message.content)
    timestamp = new_message.created_at
    updated_at = new_message.edited_at
    in_text_valid = check_intext_validity(content)

    logger.info(f"Edit event from {discord_user_id} for message id: { discord_message_id} received.",extra={"tags": {"event": "on_message_edit"}})
    try:
        # Process CP submissions for edited message
        cp_result = process_submissions(content)
        if cp_result and "error" not in cp_result:
            logger.info(f"CP submissions processed successfully for edited message from user {discord_user_id}", extra={"tags": {"event": "on_message_edit"}})
            if cp_result["solved_questions"]:
                await new_message.add_reaction("✅")
                logger.info(f"Added ✅ reaction for solved CP questions in edited message", extra={"tags": {"event": "on_message_edit"}})
        elif cp_result and "error" in cp_result:
            logger.warning(f"CP processing error in edited message: {cp_result['error']}", extra={"tags": {"event": "on_message_edit"}})

        if is_in_time_bracket(discord_user_id,timestamp) and update_log(discord_message_id, content, in_text_valid, updated_at):
            logger.info(f"Edit event from discord_user_id:{discord_user_id} for message id:{ discord_message_id} successfully patched in DB.",extra={"tags": {"event": "on_message_edit"}})
            
            await new_message.add_reaction("🛠️")
            logger.info(f"Reaction 🛠️ added to discord_user_id: {discord_user_id} for message id:{ discord_message_id}  successfully.",extra={"tags": {"event": "on_message_edit"}})
            
            messages_edited_total.inc()
        else:
            logger.info(f"Edited message from {new_message.author.name} for message id:{ discord_message_id}  could not be saved to the database.",extra={"tags": {"event": "on_message_edit"}})
            print(f"Edited message from {new_message.author.name} for message id:{ discord_message_id}  could not be saved to the database.")
            await new_message.add_reaction("👀")
            logger.warning(f"Reaction 👀 added to discord_user_id: {discord_user_id} for message id: {discord_message_id} successfully.",extra={"tags": {"event": "on_message_edit"}})
   
    except Exception as e:
        logger.error(f"Error updating message in database: {e}",extra={"tags": {"event": "on_message_edit"}})
        print(f"Error updating message in database: {e}")
        errors_encountered_total.inc()

    await bot.process_commands(new_message)

@bot.event
async def on_message_delete(message):
    if message.author == bot.user:
        return
    if message.channel.id != WATCHED_CHANNEL_ID:
        return
    # ignore arcane
    if message.author.id == 437808476106784770:
        return
   
    discord_message_id = message.id
    logger.info(f"Delete event for message id: {discord_message_id} received.",extra={"tags": {"event": "on_message_delete"}})
   
    try:
        delete_log(discord_message_id)
        logger.info(f"Message with ID {discord_message_id} was marked deleted.",extra={"tags": {"event": "on_message_delete"}})
        print(f"Message with ID {discord_message_id} was marked deleted.")
        messages_deleted_total.inc()
    except Exception as e:
        errors_encountered_total.inc()
        logger.error(f"Error deleting message from database: {e}")
        print(f"Error deleting message from database: {e}")
    await bot.process_commands(message)

bot.run(DISCORD_TOKEN)
