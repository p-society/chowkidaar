import discord # type: ignore
import sys
from loguru import logger
import asyncio
# from fastapi import FastAPI
from internal.get_environment import LoadEnv
from internal.core import client as chowkidaar_client

async def StartBot():
    await chowkidaar_client.start(token=LoadEnv().get('DISCORD_TOKEN'))
    print("deez nuts")

async def main():
    await StartBot()

asyncio.run(main())


# @Design and creative team

# Ek avatar chahiye discord bot keliye. "Chowkidaar" ka ek avatar banado profile picture keliye
# https://github.com/p-society/chowkidaar/
# Dimensions: 1024x1024 PNG and SVG Formats me

# June 1st week se start hoga 45 days event,usse pehele chahie hoga...Aaram se banao
# can take inspiration from other bots like above ones 👆

['_CACHED_SLOTS', '_HANDLERS', '__annotations__', '__class__', '__delattr__', '__dir__', '__doc__', '__eq__', '__format__', '__ge__', '__getattribute__', '__gt__', '__hash__', '__init__', '__init_subclass__', '__le__', '__lt__', '__module__', '__ne__', '__new__', '__reduce__', '__reduce_ex__', '__repr__', '__setattr__', '__sizeof__', '__slots__', '__str__', '__subclasshook__', '_add_reaction', '_clear_emoji', '_cs_channel_mentions', '_cs_clean_content', '_cs_guild', '_cs_raw_channel_mentions', '_cs_raw_mentions', '_cs_raw_role_mentions', '_cs_system_content', '_edited_timestamp', '_handle_activity', '_handle_application', '_handle_attachments', '_handle_author', '_handle_components', '_handle_content', '_handle_edited_timestamp', '_handle_embeds', '_handle_flags', '_handle_interaction', '_handle_member', '_handle_mention_everyone', '_handle_mention_roles', '_handle_mentions', '_handle_nonce', '_handle_pinned', '_handle_tts', '_handle_type', '_rebind_cached_references', '_remove_reaction', '_state', '_try_patch', '_update', 'activity', 'add_files', 'add_reaction', 'application', 'application_id', 'attachments', 'author', 'channel', 'channel_mentions', 'clean_content', 'clear_reaction', 'clear_reactions', 'components', 'content', 'create_thread', 'created_at', 'delete', 'edit', 'edited_at', 'embeds', 'fetch', 'flags', 'guild', 'id', 'interaction', 'is_system', 'jump_url', 'mention_everyone', 'mentions', 'nonce', 'pin', 'pinned', 'position', 'publish', 'raw_channel_mentions', 'raw_mentions', 'raw_role_mentions', 'reactions', 'reference', 'remove_attachments', 'remove_reaction', 'reply', 'role_mentions', 'role_subscription', 'stickers', 'system_content', 'to_message_reference_dict', 'to_reference', 'tts', 'type', 'unpin', 'webhook_id']