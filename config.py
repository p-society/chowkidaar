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

import logging as _logging

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
_watched_channel_env = os.getenv('WATCHED_CHANNEL_ID')
WATCHED_CHANNEL_ID = int(_watched_channel_env) if _watched_channel_env and _watched_channel_env.strip() else None
_contest_reminder_channel_env = os.getenv('CONTEST_REMINDER_CHANNEL_ID')
CONTEST_REMINDER_CHANNEL_ID = int(_contest_reminder_channel_env) if _contest_reminder_channel_env and _contest_reminder_channel_env.strip() else None
CONTEST_ROLE_ID = int(os.getenv('CONTEST_ROLE_ID', '0'))
CLIST_USERNAME = os.getenv('CLIST_USERNAME')
CLIST_API_KEY = os.getenv('CLIST_API_KEY')

# Surface common misconfigurations at startup. These are warnings, not
# hard errors: the bot can still boot and most features keep working,
# they'll just degrade in predictable ways.
if not WATCHED_CHANNEL_ID:
    _logging.warning(
        "WATCHED_CHANNEL_ID is unset — daily challenge announcements and dev resources are disabled."
    )
if not CONTEST_REMINDER_CHANNEL_ID:
    _logging.warning(
        "CONTEST_REMINDER_CHANNEL_ID is unset — CP contest reminders are disabled."
    )
if not CONTEST_ROLE_ID:
    _logging.warning(
        "CONTEST_ROLE_ID is unset — contest reminders will be posted without "
        "an @role mention. Set CONTEST_ROLE_ID in your .env to enable pings."
    )
if not (CLIST_USERNAME and CLIST_API_KEY):
    _logging.warning(
        "CLIST_USERNAME / CLIST_API_KEY are unset — /upcoming and the contest "
        "reminder loop will return no results. Get a key at https://clist.by/api/v4/doc/."
    )

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
