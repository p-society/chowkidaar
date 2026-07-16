"""
One-shot: clear every globally-registered slash command for this bot.

Use when you've moved to guild-scoped sync (DEV_GUILD_ID set in .env.local)
but Discord is still showing leftover global commands alongside the guild
ones, producing duplicates.

This script does NOT import main.py, so the @bot.tree.command decorators
never run, and we genuinely push an empty global command set.

Run with:
    uv run --python 3.12 scripts/clear_global_commands.py
"""

import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: F401  (loads .env.local)
import discord
from discord.ext import commands


async def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        print("DISCORD_TOKEN not set. Aborting.")
        return

    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        try:
            # No commands have been registered on this fresh Bot instance,
            # so the tree's global scope is empty. Pushing it clears Discord.
            bot.tree.clear_commands(guild=None)
            synced = await bot.tree.sync()
            print(f"Pushed empty global command set. Global commands now: {len(synced)}")
            print("Restart your main bot — guild-scoped commands will remain.")
        except Exception as e:
            print(f"Failed: {type(e).__name__}: {e}")
        finally:
            await bot.close()

    await bot.start(token)


if __name__ == "__main__":
    asyncio.run(main())
