import discord
from discord import app_commands
from discord.ext import commands
import logging as logger

from db.db import get_registered_name
from db.badges import check_and_award_milestones, format_name_with_badge
from utils.permissions import is_admin, is_watched_channel

class BadgesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="sync_badges", description="Recompute and award any milestone badges you've earned")
    @is_watched_channel()
    async def sync_badges(self, interaction: discord.Interaction, user: discord.Member | None = None):
        """
        Manual trigger for the milestone check. Useful for backfilling badges
        after manual data fixes, or for testing without waiting 7 days.
        Anyone can run it on themselves; only admins can target another member.
        """
        target = user or interaction.user

        if user is not None and user.id != interaction.user.id:
            if not is_admin(interaction):
                await interaction.response.send_message(
                    "Only admins can sync badges for another user.", ephemeral=True
                )
                return

        await interaction.response.defer()
        
        target_name = get_registered_name(target.id)
        if not target_name:
            await interaction.followup.send(
                f"❌ {target.display_name} has not registered yet. Please run `/register` first.",
                ephemeral=True
            )
            return

        try:
            newly_awarded = check_and_award_milestones(target.id)
        except Exception as e:
            logger.error(f"sync_badges failed for {target.id}: {e}")
            await interaction.followup.send(f"❌ Sync failed: {e}", ephemeral=True)
            return

        if not newly_awarded:
            await interaction.followup.send(
                f"✅ {format_name_with_badge(target.id, target_name)} is already up to date — no new badges to award.",
                ephemeral=True,
            )
            return

        # Announce any newly-earned badges (assigns role + posts a gold embed).
        for badge in newly_awarded:
            role_id = badge.get("discord_role_id")
            if role_id and interaction.guild:
                try:
                    role = interaction.guild.get_role(int(role_id))
                    if role and role not in target.roles:
                        await target.add_roles(role, reason=f"sync_badges: {badge['key']}")
                except discord.DiscordException as e:
                    logger.error(f"sync_badges role assign failed: {e}")

            embed = discord.Embed(
                title=f"🏆 New Badge: {badge['name']}",
                description=f"{target.mention} just earned **{badge['name']}** — {badge['description']}",
                color=discord.Color.gold(),
            )
            await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(BadgesCog(bot))
