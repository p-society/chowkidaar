import os
import sys
from dotenv import load_dotenv

def load_environment(env):
    if env == 'neon':
        dotenv_path = '.env.neon'
    elif env == 'local':
        dotenv_path = '.env.local'
    else:
        raise ValueError("Environment not recognized. Use 'neon' or 'local'.")
    
    load_dotenv(dotenv_path)

# Determine the environment to load
environment = os.getenv('ENVIRONMENT') or (sys.argv[1] if len(sys.argv) > 1 else 'local')
load_environment(environment)

# DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
# WATCHED_CHANNEL_ID = int(os.getenv('WATCHED_CHANNEL_ID'))
# DATABASE_NAME = os.getenv('DATABASE_NAME')
# DATABASE_USER = os.getenv('DATABASE_USER')
# DATABASE_PASSWORD = os.getenv('DATABASE_PASSWORD')
# DATABASE_HOST = os.getenv('DATABASE_HOST')

DISCORD_TOKEN='MTIzNjU3NDc4MDE1MzUzMjQ2Ng.GQGRjI.PVd23T_ncjanQ46LUDKBrnDZGiE_Ghtl8Q-yXY'
WATCHED_CHANNEL_ID=1236606978529431552
DATABASE_NAME='Chowky'
DATABASE_USER='test_owner'
DATABASE_PASSWORD='Bl7RextpY6XC'
DATABASE_HOST='ep-aged-night-a1qu8o9p.ap-southeast-1.aws.neon.tech'

if __name__ == "__main__":
    print("Using environment:", environment)
    print("DISCORD_TOKEN:", DISCORD_TOKEN)
    print("WATCHED_CHANNEL_ID:", WATCHED_CHANNEL_ID)
    print("DATABASE_NAME:", DATABASE_NAME)
    print("DATABASE_USER:", DATABASE_USER)
    print("DATABASE_PASSWORD:", DATABASE_PASSWORD)
    print("DATABASE_HOST:", DATABASE_HOST)
