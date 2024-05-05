import discord

class Chowkidaar(discord.Client):
    async def on_ready(self):
        print(f'logged in as {self.user}!')

    async def on_message(self,message):
        print(f'Message from {message.author}: {message.content}')
    
intents = discord.Intents.default()
intents.message_content = True

client = Chowkidaar(intents=intents)
