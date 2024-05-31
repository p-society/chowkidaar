import discord
import asyncio
import signal
import sys
from config import DISCORD_TOKEN, WATCHED_CHANNEL_ID
from discord.ext import commands
from db import connect_to_database, save_log, check_intext_validity
import os
from time_check import can_send_message
conn = connect_to_database()
cur = conn.cursor()

intents = discord.Intents.default()
intents.messages = True  # Ensure the bot can read messages
intents.message_content = True  # Add this line if you need access to message content

bot = commands.Bot(command_prefix="!", intents=intents)


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
        if in_text_valid == 1:
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
            print(f"Message from {message.author.name} is invalid")
            await message.add_reaction("❌")

    except Exception as e:
        print(f"Error saving message to database: {e}")
        conn.rollback()

    await bot.process_commands(message)


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
