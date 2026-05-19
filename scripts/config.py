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

# Determine the environment to load. We only treat sys.argv[1] as an env
# name when it matches one of the known values; otherwise it might be a flag
# meant for the running script (e.g. --keep) and we fall back to 'local'.
_VALID_ENVS = ('neon', 'local')
_argv_env = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] in _VALID_ENVS else None
environment = os.getenv('ENVIRONMENT') or _argv_env or 'local'
load_environment(environment)

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
WATCHED_CHANNEL_ID = int(os.getenv('WATCHED_CHANNEL_ID'))

# Postgres connection settings. The .env files use POSTGRES_* names
# (matching docker-compose conventions); expose them under both
# POSTGRES_* and the legacy DATABASE_* aliases that other modules import.
POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_DB = os.getenv('POSTGRES_DB')
POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
NEON_DB_URL = os.getenv('NEON_DB_URL')

DATABASE_NAME = POSTGRES_DB
DATABASE_USER = POSTGRES_USER
DATABASE_PASSWORD = POSTGRES_PASSWORD
DATABASE_HOST = POSTGRES_HOST


if __name__ == "__main__":
    print("Using environment:", environment)
    print("DISCORD_TOKEN:", DISCORD_TOKEN)
    print("WATCHED_CHANNEL_ID:", WATCHED_CHANNEL_ID)
    print("DATABASE_NAME:", DATABASE_NAME)
    print("DATABASE_USER:", DATABASE_USER)
    print("DATABASE_PASSWORD:", DATABASE_PASSWORD)
    print("DATABASE_HOST:", DATABASE_HOST)
