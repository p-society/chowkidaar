import discord

class Chowkidaar(discord.Client):
    async def on_ready(self):
        print(f'logged in as {self.user}!')

    async def on_message(self,message):
        print(f'Message from {message.author}: {message.content} {self.latency} ')
        v = dir(message.author)
        print(f'Message from {message.author}: {message.content} {message.channel}')
        print(f'Username: {message.author.name}')
        print(f'Discriminator: {message.author.discriminator}')
        print(f'Avatar URL: {message.author.avatar}')
        print(f'Account created at: {message.author.created_at}')
        print(f'Display Name: {message.author.display_name}')

    async def on_message_edit(self, before, after):
        # Print information about the edited message
        print(f'Message edited by {after.author}:')
        print(f'Before: {before.content}')
        print(f'After: {after.content}')
        print(f'Edit time: {after.edited_at}')
    
    async def on_message_delete(self, before, after):
        # Print information about the edited message
        print("lol")
        print(f'Message edited by {after.author}:')
        print(f'Before: {before.content}')
        print(f'After: {after.content}')
        print(f'Edit time: {after.edited_at}')
    


intents = discord.Intents.default()
intents.message_content = True

client = Chowkidaar(intents=intents)