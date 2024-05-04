import discord # type: ignore
import sys
from loguru import logger
import asyncio
from fastapi import FastAPI

config_file = open(".env","r")
env = {}

for line in config_file:
    k,v = line.split('=')
    env[k]=v

class EnvNotFound(Exception):
    def __init__(self, notFoundEnv):
        self.message = f'[ERROR]: env variable for {notFoundEnv} not found in .env'
        super().__init__(self.message)

config_file.close()

try:
    token = env.get('DISCORD_TOKEN')
    if(token == None): 
        raise EnvNotFound('DISCORD_TOKEN') 
except Exception as e:
    logger.error(e.message)
    logger.error(e.message)
    sys.exit(1)


class MyClient(discord.Client):
    async def on_ready(self):
        print(f'logged on as {self.user}!')

    async def on_message(self,message):
        print(f'Message from {message.author}: {message.content}')
    
intents = discord.Intents.default()
intents.message_content = True

client = MyClient(intents=intents)

async def StartBot():
    await client.start(token=env.get('DISCORD_TOKEN'))

asyncio.run(StartBot())
print("deez nuts")

# app: FastAPI = FastAPI()

# @app.get('/')
# def read_root():
#     return {
#         "Hello":"World"
#     }
    


# ### Requirements
# '''
#     MVP
#     1. User can type out their progress
#     2. Application will keep an eye on the messages received on the channels
#     3.(i) If a message has a ID (getting ID after searching/parsing) -> make a API Request to update user
#     s progress in PostgreSQL
#       (ii) If a message doesnt has a ID -> leave the message
    
#     EXTRAS
#     4. Make some statistics,graphs,etc 
# '''

