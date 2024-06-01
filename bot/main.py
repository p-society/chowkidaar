import discord
import asyncio
import signal
import sys
from config import DISCORD_TOKEN, WATCHED_CHANNEL_ID
from discord.ext import commands
from db import connect_to_database, save_log, check_intext_validity, update_log
import os
from time_check import can_send_message, is_in_time_bracket
conn = connect_to_database()
cur = conn.cursor()

intents = discord.Intents.default()
intents.messages = True  # Ensure the bot can read messages
intents.message_content = True  # Add this line if you need access to message content

bot = commands.Bot(command_prefix="!", intents=intents)
bot.activity = discord.Activity(type=discord.ActivityType.watching, name="for message updates")


@bot.event
async def on_ready():
    print(f"Bot is ready. Logged in as {bot.user}")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    if message.channel.id != WATCHED_CHANNEL_ID:
        return

    discord_user_id = message.author.id
    discord_message_id = message.id
    content = str(message.content)
    timestamp = message.created_at
# <<<<<<< time-checks
    
#     try: 
#         # if in_text_valid == 1:
#         if can_send_message(discord_user_id=discord_user_id,msg_sending_time=timestamp,conn=conn):
#             save_log(conn, content, discord_user_id, discord_message_id, timestamp ,in_text_valid=-1)
# =======
    in_text_valid = check_intext_validity(conn, content)

    try:
        if can_send_message(discord_user_id, timestamp, conn):
            save_log(
                conn,
                content,
                discord_user_id,
                discord_message_id,
                timestamp,
                in_text_valid,
            )
# >>>>>>> main
            print(f"Message from {message.author.name} saved to the database.")
            await message.add_reaction("🎊")
        else:
            print(f"Message from {message.author.name} could not be saved to the database.")
            await message.add_reaction("❌")

    except Exception as e:
        print(f"Error saving message to database: {e}")
        conn.rollback()

    await bot.process_commands(message)

@bot.event
async def on_message_edit(old_message, new_message):
    print("Message edited.")
    if new_message.author == bot.user:
        return

    if new_message.channel.id != WATCHED_CHANNEL_ID:
        return

    discord_user_id = new_message.author.id
    discord_message_id = new_message.id
    content = str(new_message.content)
    timestamp = new_message.created_at
    updated_at = new_message.edited_at
    in_text_valid = check_intext_validity(conn, content)

    try:
        if is_in_time_bracket(timestamp):
            update_log(conn, discord_message_id, content, in_text_valid, updated_at)
            await new_message.add_reaction("🛠️")
        else:
            print(f"Edited message from {new_message.author.name} could not be saved to the database.")
            await new_message.add_reaction("❗")

    except Exception as e:
        print(f"Error updating message in database: {e}")
        conn.rollback()
    
    await bot.process_commands(new_message)
    


# async def shutdown(signal, frame):
#     print("Shutting down bot and closing database connection...")
#     await bot.close()
#     cur.close()
#     conn.close()
#     sys.exit(0)

# # Catch termination signals to ensure graceful shutdown
# signal.signal(signal.SIGINT, lambda s, f: asyncio.create_task(shutdown(s, f)))
# signal.signal(signal.SIGTERM, lambda s, f: asyncio.create_task(shutdown(s, f)))


bot.run(DISCORD_TOKEN)
