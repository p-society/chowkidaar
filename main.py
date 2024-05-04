import discord # type: ignore
import sys
from loguru import logger
import asyncio
from fastapi import FastAPI
from get_environment import LoadEnv
from core import client as chowkidaar_client

async def StartBot():
    await chowkidaar_client.start(token=LoadEnv().get('DISCORD_TOKEN'))
    print("deez nuts")

async def main():
    await StartBot()

asyncio.run(main())