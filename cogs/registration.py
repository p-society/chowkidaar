import io
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
import logging as logger

from db.db import register_user, get_student_profile, connect_to_database
from db.badges import format_name_with_badge, count_distinct_submission_days, current_streak, list_user_badges
from utils.card_generator import CardData, render_card
from utils.event_window import get_event_window
from utils.permissions import is_watched_channel

def _fetch_profile_data_tx(discord_user_id: int, start_utc, end_utc):
    conn = connect_to_database(purpose="Load Student Profile & Badges")
    if not conn:
        return None
    try:
        # 1. Fetch student profile
        profile = None
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT stu_id, name, COALESCE(total_solved, 0)
                FROM student_list_2024
                WHERE discord_user_id = %s
                LIMIT 1
                """,
                (discord_user_id,),
            )
            row = cur.fetchone()
            if row:
                profile = {"stu_id": row[0], "name": row[1], "total_solved": row[2]}
        
        if not profile:
            return None

        # 2. Get day progress
        day_progress = count_distinct_submission_days(discord_user_id, start_utc, end_utc, conn=conn)

        # 3. Get current streak
        streak = current_streak(discord_user_id, conn=conn)

        # 4. Get badge rows
        badge_rows = list_user_badges(discord_user_id, conn=conn)

        # 5. Extract badge emojis directly in Python, sorted by display_priority
        badge_emojis = [
            b["emoji"]
            for b in sorted(badge_rows, key=lambda x: x.get("display_priority", 9999))
            if b.get("emoji")
        ]

        return {
            "profile": profile,
            "day_progress": day_progress,
            "streak": streak,
            "badge_rows": badge_rows,
            "badge_emojis": badge_emojis
        }
    finally:
        conn.close()


class RegistrationCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="register", description="Register your CP handles")
    @is_watched_channel()
    async def register(self, interaction: discord.Interaction, student_id: str, name: str, leetcode_handle: str, codeforces_handle: str):
        # Capture the caller's Discord ID so we can link stu_id <-> discord later
        # (used for badges, contest points, etc.).
        success = await asyncio.to_thread(
            register_user,
            student_id, name, leetcode_handle, codeforces_handle,
            discord_user_id=interaction.user.id,
        )
        
        embed = discord.Embed(title="Registration Status", color=discord.Color.green() if success else discord.Color.red())
        if success:
            embed.description = "✅ User registered successfully!"
            embed.add_field(name="Name", value=name, inline=True)
            embed.add_field(name="Student ID", value=student_id, inline=True)
            embed.add_field(name="LeetCode", value=leetcode_handle, inline=True)
            embed.add_field(name="CodeForces", value=codeforces_handle, inline=True)
        else:
            embed.description = "❌ Failed to register user. Please try again or contact an admin."
            
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="profile", description="View your progress, badges, and generate a shareable card")
    @is_watched_channel()
    async def profile(self, interaction: discord.Interaction, user: discord.Member | None = None):
        """Shows a rich embed with progress bars, badges, and the shareable card."""
        target = user or interaction.user
        await interaction.response.defer()

        start_utc, end_utc = get_event_window()
        data_res = await asyncio.to_thread(_fetch_profile_data_tx, target.id, start_utc, end_utc)
        if not data_res:
            await interaction.followup.send(
                f"❌ {target.display_name} hasn't registered yet.",
                ephemeral=True,
            )
            return

        profile = data_res["profile"]
        day_progress = data_res["day_progress"]
        streak = data_res["streak"]
        badge_rows = data_res["badge_rows"]
        badge_emojis = data_res["badge_emojis"]
        total_solved = profile["total_solved"]

        embed = discord.Embed(
            title=f"{format_name_with_badge(target.id, profile['name'])}",
            color=discord.Color.teal(),
        )

        # Progress bar (25 days total)
        duration_days = 25
        filled = min(day_progress, duration_days)
        empty = duration_days - filled
        progress_bar = (
            f"[{'█' * filled}{'░' * empty}] {day_progress}/{duration_days} Days"
        )

        embed.add_field(name="Progress", value=progress_bar, inline=False)
        embed.add_field(name="🔥 Streak", value=str(streak), inline=True)
        embed.add_field(name="✅ Total Solved", value=str(total_solved), inline=True)

        if not badge_rows:
            embed.add_field(
                name="🏆 Badges",
                value="No badges yet. Keep submitting!",
                inline=False,
            )
        else:
            badge_text = ""
            for b in badge_rows:
                awarded = b["awarded_at"].strftime("%Y-%m-%d")
                emoji_prefix = f"{b['emoji']} " if b.get("emoji") else ""
                badge_text += f"{emoji_prefix}**{b['name']}**: {b['description']} *(awarded {awarded})*\n\n"
            embed.add_field(name="🏆 Badges", value=badge_text, inline=False)

        avatar_bytes: bytes | None = None
        try:
            asset = target.display_avatar.with_size(512).with_format("webp")
            avatar_bytes = await asset.read()
        except Exception as e:
            logger.error(f"Failed to download avatar for {target.id}: {e}")

        data = CardData(
            name=profile["name"],
            student_id=profile["stu_id"],
            day_progress=day_progress,
            streak=streak,
            total_solved=total_solved,
            badge_emojis=badge_emojis,
            badge_keys=[b["key"] for b in badge_rows],
            avatar_webp_bytes=avatar_bytes,
        )

        try:
            webp_bytes = await asyncio.to_thread(render_card, data)
        except Exception as e:
            logger.error(f"Card render failed for {target.id}: {e}")
            await interaction.followup.send(
                f"❌ Card render failed: {e}", ephemeral=True
            )
            return

        # Image attachment handling
        filename = f"chowkidaar_card_{profile['stu_id']}.webp"
        file = discord.File(io.BytesIO(webp_bytes), filename=filename)
        embed.set_image(url=f"attachment://{filename}")

        # 2. Attach the sharing text directly into the Footer slot
        # Note: Text formatting characters like * or ** are omitted since footers display plain text
        footer_text = "Feel free to share your profile card on Instagram or Twitter/X!\n(Long press / Right click the image to save)"
        embed.set_footer(text=footer_text)

        # Fire message response
        await interaction.followup.send(
            embed=embed,
            file=file,
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(RegistrationCog(bot))
