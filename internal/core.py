from datetime import datetime
import uuid
import discord
from internal.parse_message import extract_user_info
from internal.user_service import User_Service
from internal.participation_log_service import Participation_Log_Service
class Chowkidaar(discord.Client):
    async def on_ready(self):
        print(f'Logged in as {self.user}!')

    async def on_message(self, message):
        try:
            name, college_id = extract_user_info(message.content)
            data = {
                "id": str(uuid.uuid4()),  
                "college_id": college_id,
                "discord_username": message.author.name[:50],
                "discriminator": message.author.discriminator,
                "avatar_url": str(message.author.avatar), 
                "account_created_at": message.author.created_at,
                "display_name": message.author.display_name,
                "branch": college_id[1], 
                "email": f"{college_id}@iiit-bh.ac.in",
            }
            user_service = User_Service()
            user_id = user_service.save_to_db(data)
            
            # participation_log_data = {
            #    "id": str(uuid.uuid4()),
            #    "sent_at": datetime.now(),
            #    "message":message.content,
            #    "user_id": user_id
            # }
            
            # participation_log_service = Participation_Log_Service()
            # participation_log_service.save_to_db(participation_log_data)
                        
        except Exception as e:
            print("err:",e)

    async def on_message_edit(self, before, after):
        print(f'Message edited by {after.author}:') 
        print(f'Before: {before.content}')
        print(f'After: {after.content}')
        print(f'Edit time: {after.edited_at}')
    
    async def on_message_delete(self, before, after):
        print("lol")
        print(f'Message edited by {after.author}:')
        print(f'Before: {before.content}')
        print(f'After: {after.content}')
        print(f'Edit time: {after.edited_at}')
    


intents = discord.Intents.default()
intents.message_content = True

client = Chowkidaar(intents=intents)