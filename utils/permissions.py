"""
Bot-level permissions.

We keep an allow-list of Discord user IDs in configs/event_config.json under
"bot_admins". These users can run admin slash commands (e.g. /sync_badges
for another user, /grant_badge) regardless of their Discord server role.

Discord *server* admins (guild_permissions.administrator) are also treated
as bot admins automatically — combining both checks via is_admin().
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import TYPE_CHECKING, Set

if TYPE_CHECKING:  # imported only for static type hints; not needed at runtime
    import discord

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "configs",
    "event_config.json",
)


@lru_cache(maxsize=1)
def _load_admins() -> Set[int]:
    try:
        with open(_CONFIG_PATH, "r") as f:
            cfg = json.load(f)
    except FileNotFoundError:
        return set()
    return {int(uid) for uid in cfg.get("bot_admins", [])}


def reload_admins() -> None:
    """Clear the cache so the next is_bot_admin() call re-reads the file."""
    _load_admins.cache_clear()


def is_bot_admin(discord_user_id: int) -> bool:
    """True if the Discord user is in the bot_admins allow-list."""
    return int(discord_user_id) in _load_admins()


def is_admin(interaction: discord.Interaction) -> bool:
    """
    Combined check: True if the caller is in the bot_admins allow-list,
    OR has Discord server administrator permissions in the current guild.
    """
    if is_bot_admin(interaction.user.id):
        return True
    if interaction.guild and interaction.user.guild_permissions.administrator:
        return True
    return False


def is_watched_channel():
    import discord
    from discord import app_commands
    def predicate(interaction: discord.Interaction) -> bool:
        return True
    return app_commands.check(predicate)

