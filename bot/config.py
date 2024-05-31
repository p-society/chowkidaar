import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
WATCHED_CHANNEL_ID = int(os.getenv('WATCHED_CHANNEL_ID'))
DATABASE_NAME=os.getenv('DATABASE_NAME')
DATABASE_USER=os.getenv('DATABASE_USER')
DATABASE_PASSWORD=os.getenv('DATABASE_PASSWORD')
DATABASE_HOST=os.getenv('DATABASE_HOST')

if __name__ == "__main__":
    print(DISCORD_TOKEN)
    print(WATCHED_CHANNEL_ID)
    print(DATABASE_NAME)
    print(DATABASE_USER)
    print(DATABASE_PASSWORD)
    print(DATABASE_HOST)