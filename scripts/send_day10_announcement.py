import os
import sys
import asyncio
import discord
from dotenv import load_dotenv

# Add parent directory to path so we can import from configs/daily_resources
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from daily_resources.daily_questions import (
    load_questions,
    load_event_config,
    create_daily_question_embed,
)
from daily_resources.dev_resources import (
    load_dev_resources,
    create_dev_resources_embed,
)

load_dotenv(dotenv_path=".env.local")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
WATCHED_CHANNEL_ID = os.getenv("WATCHED_CHANNEL_ID")

if not DISCORD_TOKEN or not WATCHED_CHANNEL_ID:
    print("Error: DISCORD_TOKEN or WATCHED_CHANNEL_ID is not set in .env.local")
    sys.exit(1)

class AnnouncementClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        channel_id = int(WATCHED_CHANNEL_ID)
        channel = self.get_channel(channel_id)
        if not channel:
            try:
                channel = await self.fetch_channel(channel_id)
            except Exception as e:
                print(f"Failed to fetch channel {channel_id}: {e}")
                await self.close()
                return

        print(f"Sending Day 10 announcement to channel: {channel.name} ({channel.id})")

        # 1. Create Extension Announcement Embed
        announcement_embed = discord.Embed(
            title="📢 Submission Deadline Extension (Day 9) & Day 10 Release",
            description=(
                "Last night, the Codeforces API experienced an outage, preventing submissions from working correctly for several hours. "
                "To compensate and ensure no one loses their streak, we have extended the submission window:\n\n"
                "⏰ **Day 9 Submission Deadline has been extended by 6 hours!**\n"
                "New Deadline: **Today (June 10) at 6:00 PM IST** (instead of 12:00 PM Noon).\n\n"
                "Thank you for your patience! Below are the Day 10 questions and resources."
            ),
            color=discord.Color.gold()
        )
        announcement_embed.set_footer(text="The Programming Society · IIIT-BH")

        # 2. Create Day 10 Question Embed
        questions = load_questions()
        config = load_event_config()
        day_str = "10"
        
        q_embed = None
        if day_str in questions:
            q_embed = create_daily_question_embed(10, questions[day_str], config)
        else:
            print("Warning: Day 10 questions not found in questions.json")

        # 3. Create Day 10 Dev Resources Embed
        dev_resources = load_dev_resources()
        r_embed = None
        if day_str in dev_resources:
            r_embed = create_dev_resources_embed(10, dev_resources[day_str], config)
        else:
            print("Warning: Day 10 dev resources not found in dev.json")

        # Send messages
        try:
            # Unpin previous messages if needed
            try:
                pinned_messages = await channel.pins()
                bot_id = self.user.id
                for pinned in pinned_messages:
                    if pinned.author.id == bot_id:
                        content = pinned.content or ""
                        if pinned.embeds:
                            content += " " + (pinned.embeds[0].title or "") + " " + (pinned.embeds[0].description or "")
                        if "Day " in content and not "Day 10" in content:
                            try:
                                await pinned.unpin()
                                print(f"Unpinned old message: {pinned.id}")
                            except Exception as unpin_err:
                                print(f"Failed to unpin message {pinned.id}: {unpin_err}")
            except Exception as pins_fetch_err:
                print(f"Failed to fetch or process pinned messages: {pins_fetch_err}")

            # Send the announcement message
            try:
                ann_msg = await channel.send(embed=announcement_embed)
                print("Extension announcement sent.")
            except Exception as send_ann_err:
                print(f"Failed to send announcement: {send_ann_err}")

            # Send and pin Day 10 questions
            if q_embed:
                try:
                    q_msg = await channel.send(embed=q_embed)
                    print("Day 10 questions sent.")
                    try:
                        await q_msg.pin()
                        print("Day 10 questions pinned.")
                    except Exception as pin_err:
                        print(f"Failed to pin Day 10 questions: {pin_err}")
                except Exception as send_q_err:
                    print(f"Failed to send Day 10 questions: {send_q_err}")

            # Send and pin Day 10 resources
            if r_embed:
                try:
                    r_msg = await channel.send(embed=r_embed)
                    print("Day 10 dev resources sent.")
                    try:
                        await r_msg.pin()
                        print("Day 10 dev resources pinned.")
                    except Exception as pin_err:
                        print(f"Failed to pin Day 10 dev resources: {pin_err}")
                except Exception as send_r_err:
                    print(f"Failed to send Day 10 dev resources: {send_r_err}")

        except Exception as e:
            print(f"Error in announcement execution: {e}")

        await self.close()

if __name__ == "__main__":
    client = AnnouncementClient()
    client.run(DISCORD_TOKEN)
