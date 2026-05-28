import discord
from discord import app_commands
from discord.ext import commands, tasks
import logging as logger
import asyncio

from db.db import get_registered_name
from db.badges import check_and_award_milestones, format_name_with_badge, list_user_badges
from utils.permissions import is_admin, is_watched_channel

def _fetch_active_user_ids() -> set[int]:
    from db.db import connect_to_database
    conn = connect_to_database(purpose="Fetch Active User IDs for Badge Sync")
    if not conn:
        return set()
    user_ids: set[int] = set()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT discord_user_id
                FROM participation_logs
                WHERE deleted_at IS NULL
                  AND discord_user_id IS NOT NULL
                """
            )
            user_ids.update(r[0] for r in cur.fetchall())
            cur.execute(
                """
                SELECT discord_user_id
                FROM student_list_2024
                WHERE discord_user_id IS NOT NULL
                """
            )
            user_ids.update(r[0] for r in cur.fetchall())
        return user_ids
    except Exception as e:
        logger.error(f"Error fetching active user IDs: {e}")
        return set()
    finally:
        conn.close()


def _batch_award_milestones_tx(user_ids: set[int]):
    from db.db import connect_to_database
    conn = connect_to_database(purpose="Batch Milestone Badge Check & Award")
    if not conn:
        return {}, {}
    user_newly_badges = {}
    user_all_badges = {}
    try:
        for uid in user_ids:
            try:
                user_newly_badges[uid] = check_and_award_milestones(uid, conn=conn)
                user_all_badges[uid] = list_user_badges(uid, conn=conn)
            except Exception as e:
                logger.error(f"batch milestone award error for {uid}: {e}")
        return user_newly_badges, user_all_badges
    finally:
        conn.close()


class BadgesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.automated_badge_sync_loop.start()

    def cog_unload(self):
        self.automated_badge_sync_loop.cancel()

    @tasks.loop(hours=4)
    async def automated_badge_sync_loop(self):
        """
        Self-healing background task running every 4 hours to recompute milestone
        badges and reconcile Discord roles for all active users.
        """
        logger.info("Starting automated badge and role sync loop...")
        try:
            # 1. Fetch active users in a separate thread
            user_ids = await asyncio.to_thread(_fetch_active_user_ids)
            if not user_ids:
                logger.info("Automated badge sync: No users to sync.")
                return

            # 2. Run the database checks and awards in a consolidated thread
            user_newly_badges, user_all_badges = await asyncio.to_thread(
                _batch_award_milestones_tx, user_ids
            )

            # 3. Reconcile Discord roles for each user
            for guild in self.bot.guilds:
                for uid in user_ids:
                    # Fetch student's badges from our pre-fetched dict
                    all_badges = user_all_badges.get(uid, [])
                    if not all_badges:
                        continue

                    # Get member
                    member = guild.get_member(uid)
                    if member is None:
                        try:
                            member = await guild.fetch_member(uid)
                        except discord.NotFound:
                            continue
                        except discord.HTTPException as e:
                            logger.error(f"Automated sync: fetch_member failed for {uid}: {e}")
                            continue

                    for badge in all_badges:
                        role_id = badge.get("discord_role_id")
                        if not role_id:
                            continue

                        role = guild.get_role(int(role_id))
                        if role is None:
                            continue

                        if role in member.roles:
                            continue

                        try:
                            await member.add_roles(role, reason=f"automated_badge_sync: {badge['key']}")
                            logger.info(f"Automated sync: Assigned role {role.name} to {member.display_name}")
                            # Sleep to prevent hitting Discord API rate limits
                            await asyncio.sleep(0.5)
                        except discord.DiscordException as e:
                            logger.error(f"Automated sync: role assign failed for {uid}/{badge['key']}: {e}")

        except Exception as e:
            logger.error(f"Error in automated_badge_sync_loop: {e}")

    @automated_badge_sync_loop.before_loop
    async def before_automated_badge_sync_loop(self):
        await self.bot.wait_until_ready()

    @app_commands.command(
        name="sync_badges",
        description="(admin) Recompute streak-based milestone badges for every user",
    )
    @is_watched_channel()
    async def sync_badges(self, interaction: discord.Interaction):
        """
        Admin-only batch sync.

        Walks every Discord user that has either submitted (rows in
        participation_logs) or registered (a row in student_list_2024 with a
        discord_user_id), recomputes their max streak, and awards any
        milestone badges they qualify for but don't already have. Idempotent
        — re-running won't duplicate badges.

        For each newly-awarded badge, also assigns the corresponding Discord
        role (if one is configured) and bumps the user's role list.

        Replies with an ephemeral summary to the admin who ran it. No public
        channel spam.
        """
        if not is_admin(interaction):
            await interaction.response.send_message(
                "Admins only.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Fetch active user IDs in a thread
        user_ids = await asyncio.to_thread(_fetch_active_user_ids)
        if not user_ids:
            await interaction.followup.send(
                "No users to sync — nobody has submitted or registered with a Discord ID.",
                ephemeral=True,
            )
            return

        # Perform all database lookups in a single transaction in a separate thread
        user_newly_badges, user_all_badges = await asyncio.to_thread(
            _batch_award_milestones_tx, user_ids
        )

        summary: dict[str, list[int]] = {}     # badge_key -> [discord_user_id, ...]
        role_failures = 0
        roles_added = 0                        # successful add_roles calls
        members_not_in_guild = 0               # uid not findable in the guild
        roles_already_held = 0                 # member already had the badge role
        roles_missing_in_guild = 0             # discord_role_id is set but role doesn't exist in the guild
        badges_without_role_id = 0             # badge has no discord_role_id mapping

        if not interaction.guild:
            await interaction.followup.send("❌ Guild context not found.", ephemeral=True)
            return

        for uid in user_ids:
            newly = user_newly_badges.get(uid, [])
            for badge in newly:
                summary.setdefault(badge["key"], []).append(uid)

            all_badges = user_all_badges.get(uid, [])
            if not all_badges:
                continue

            # Try cache first; fall back to a one-shot fetch_member API call.
            member = interaction.guild.get_member(uid)
            if member is None:
                try:
                    member = await interaction.guild.fetch_member(uid)
                except discord.NotFound:
                    members_not_in_guild += 1
                    continue
                except discord.HTTPException as e:
                    logger.error(f"sync_badges: fetch_member failed for {uid}: {e}")
                    members_not_in_guild += 1
                    continue

            for badge in all_badges:
                role_id = badge.get("discord_role_id")
                if not role_id:
                    badges_without_role_id += 1
                    continue

                role = interaction.guild.get_role(int(role_id))
                if role is None:
                    roles_missing_in_guild += 1
                    logger.error(
                        f"sync_badges: role id {role_id} for badge {badge['key']} "
                        f"not found in guild {interaction.guild.id}"
                    )
                    continue

                if role in member.roles:
                    roles_already_held += 1
                    continue

                try:
                    await member.add_roles(role, reason=f"sync_badges: {badge['key']}")
                    roles_added += 1
                    await asyncio.sleep(0.5)  # rate limit safety
                except discord.DiscordException as e:
                    role_failures += 1
                    logger.error(
                        f"sync_badges role assign failed for {uid}/{badge['key']}: {e}"
                    )

        # Build the ephemeral admin summary.
        lines = [f"✅ Synced **{len(user_ids)}** user(s)."]
        if summary:
            lines.append("New badges awarded:")
            for badge_key in sorted(summary):
                lines.append(f"• `{badge_key}` x {len(summary[badge_key])}")
        else:
            lines.append("No new badges to award — everyone is already up to date.")

        lines.append("")
        lines.append("Role reconciliation:")
        lines.append(f"• ✅ added: **{roles_added}**")
        lines.append(f"• ⏭️ already held: {roles_already_held}")
        lines.append(f"• 👤 user not in guild: {members_not_in_guild}")
        lines.append(f"• 🪪 badge missing discord_role_id: {badges_without_role_id}")
        lines.append(f"• 🔍 role id set but not found in guild: {roles_missing_in_guild}")

        if role_failures:
            lines.append(
                f"\n⚠️ {role_failures} Discord role assignment(s) failed — likely missing "
                f"`Manage Roles` permission or the bot's role sits below the badge role."
            )

        await interaction.followup.send("\n".join(lines), ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(BadgesCog(bot))
