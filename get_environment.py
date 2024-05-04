from loguru import logger
from errors import EnvNotFound
import sys

def LoadEnv()-> dict:
    config_file = open(".env","r")
    env_set = {}
    for line in config_file:
        k,v = line.split('=')
        env_set[k]=v
    config_file.close()
    try:
        return env_set
    except Exception as e:
        logger.error(e.message)
        logger.error(e.message)
        sys.exit(1)