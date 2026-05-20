import discord
from discord import app_commands
from discord.ext import commands
import logging as logger

from db.db import get_registered_name
from db.badges import check_and_award_milestones, format_name_with_badge, list_user_badges
from utils.permissions import is_admin, is_watched_channel

class BadgesCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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

        # Collect every distinct Discord user we know about: anyone who has
        # ever submitted OR who has a discord_user_id on their student record.
        from db.db import connect_to_database
        conn = connect_to_database()
        if not conn:
            await interaction.followup.send("❌ DB connection failed.", ephemeral=True)
            return

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
        finally:
            conn.close()

        if not user_ids:
            await interaction.followup.send(
                "No users to sync — nobody has submitted or registered with a Discord ID.",
                ephemeral=True,
            )
            return

        summary: dict[str, list[int]] = {}     # badge_key -> [discord_user_id, ...]
        role_failures = 0
        check_errors = 0
        roles_added = 0                        # successful add_roles calls
        members_not_in_guild = 0               # uid not findable in the guild
        roles_already_held = 0                 # member already had the badge role
        roles_missing_in_guild = 0             # discord_role_id is set but role doesn't exist in the guild
        badges_without_role_id = 0             # badge has no discord_role_id mapping

        for uid in user_ids:
            # ── Phase A: award any newly-earned milestone badges ──────────
            try:
                newly = check_and_award_milestones(uid)
            except Exception as e:
                check_errors += 1
                logger.error(f"sync_badges: milestone check failed for {uid}: {e}")
                continue

            for badge in newly:
                summary.setdefault(badge["key"], []).append(uid)

            # ── Phase B: reconcile Discord roles against ALL of this user's
            # badges (not just the newly-awarded ones). Idempotent — if the
            # member already has the role, member.add_roles is a no-op on the
            # Discord side; we skip the call via the `role not in member.roles`
            # guard to avoid wasted API traffic.
            if not interaction.guild:
                continue

            # Try cache first; fall back to a one-shot fetch_member API call.
            # fetch_member works even without the privileged members intent.
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

            for badge in list_user_badges(uid):
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
                except discord.DiscordException as e:
                    role_failures += 1
                    logger.error(
                        f"sync_badges role assign failed for {uid}/{badge['key']}: {e}"
                    )

        # Build the ephemeral admin summary. We always include the diagnostic
        # counters so it's obvious where role assignment is or isn't happening.
        lines = [f"✅ Synced **{len(user_ids)}** user(s)."]
        if summary:
            lines.append("New badges awarded:")
            for badge_key in sorted(summary):
                lines.append(f"• `{badge_key}` × {len(summary[badge_key])}")
        else:
            lines.append("No new badges to award — everyone is already up to date.")

        lines.append("")
        lines.append("Role reconciliation:")
        lines.append(f"• ✅ added: **{roles_added}**")
        lines.append(f"• ⏭️ already held: {roles_already_held}")
        lines.append(f"• 👤 user not in guild: {members_not_in_guild}")
        lines.append(f"• 🪪 badge missing discord_role_id: {badges_without_role_id}")
        lines.append(f"• 🔍 role id set but not found in guild: {roles_missing_in_guild}")

        if check_errors:
            lines.append(f"\n⚠️ {check_errors} user(s) errored during the milestone check (see bot logs).")
        if role_failures:
            lines.append(
                f"⚠️ {role_failures} Discord role assignment(s) failed — likely missing "
                f"`Manage Roles` permission or the bot's role sits below the badge role."
            )

        await interaction.followup.send("\n".join(lines), ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(BadgesCog(bot))
