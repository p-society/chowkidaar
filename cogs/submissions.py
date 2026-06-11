import discord
import asyncio
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
import logging as logger

from db.db import save_log, update_log, delete_cp_log, get_student_profile, update_cp_log_by_day
from db.badges import check_and_award_milestones, format_name_with_badge
from db.contests import record_user_contests
from db.slash_commands_cp import process_slash_submission, get_user_status
from db.submission_queue import enqueue_submission, has_pending_entry, update_queued_description
from utils.permissions import is_watched_channel
from utils.time_check import is_in_time_bracket
from utils.metrics import messages_sent_total, messages_edited_total

from utils.submission_utils import make_question_link, create_submission_embed

async def announce_badges(interaction: discord.Interaction, badges: list[dict]) -> None:
    """
    For each newly-awarded badge: assign the Discord role (if discord_role_id
    is configured for that badge) and post a celebration embed in the
    interaction channel. Failures are swallowed with a log — a missing role
    must not break the /submit response.
    """
    if not badges:
        return

    member = interaction.guild.get_member(interaction.user.id) if interaction.guild else None

    for badge in badges:
        role_id = badge.get("discord_role_id")
        if role_id and member:
            try:
                role = interaction.guild.get_role(int(role_id))
                if role and role not in member.roles:
                    await member.add_roles(role, reason=f"Earned badge: {badge['key']}")
            except discord.DiscordException as e:
                logger.error(f"Failed to assign role for badge {badge['key']}: {e}")

        embed = discord.Embed(
            title=f"🏆 New Badge: {badge['name']}",
            description=f"{interaction.user.mention} just earned **{badge['name']}** — {badge['description']}",
            color=discord.Color.gold(),
        )
        try:
            await interaction.followup.send(embed=embed)
        except discord.DiscordException as e:
            logger.error(f"Failed to send badge embed for {badge['key']}: {e}")

class SubmissionsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="submit", description="Submit your daily CP progress")
    @is_watched_channel()
    async def submit(self, interaction: discord.Interaction, student_id: str, day: int, description: str):
        await interaction.response.defer()

        # Pre-initialize side-effect outputs so the embed/announcement code
        # below is safe even if the CP submission errors out before we get
        # a chance to compute them.
        newly_awarded: list[dict] = []
        new_contests: list = []
        contest_badges: list[dict] = []

        # Process CP submissions
        cp_result = await asyncio.to_thread(process_slash_submission, student_id, day)

        #  Queue fallback: if an external API is down, enqueue for retry 
        if cp_result.get("queue_required"):
            await asyncio.to_thread(
                enqueue_submission,
                user_id=student_id,
                discord_user_id=interaction.user.id,
                day=day,
                description=description,
                submitted_at=interaction.created_at,
                failed_platform=cp_result["failed_platform"],
                error_msg=cp_result.get("error_message", ""),
            )
            embed = discord.Embed(
                title=f"📬 Day {day} Submission Queued",
                description=(
                    "Your submission is recorded but the server is currently down.\n"
                    "It will be verified automatically once the server is up. Thank you!"
                ),
                color=discord.Color.yellow(),
            )
            embed.add_field(name="Student ID", value=student_id, inline=True)
            embed.add_field(name="Day", value=str(day), inline=True)
            embed.add_field(name="Platform Down", value=cp_result["failed_platform"].title(), inline=True)
            await interaction.followup.send(embed=embed)
            return

        is_legal_time = True
        if "error" not in cp_result:
            # Time bracket check
            from db.db import flag_late
            is_legal_time = is_in_time_bracket(day, datetime.now(timezone.utc))
            if not is_legal_time:
                await asyncio.to_thread(flag_late, student_id)

            # Save log
            await asyncio.to_thread(
                save_log,
                description, interaction.user.id, interaction.id, interaction.created_at, 1
            )
            messages_sent_total.inc()

            # Milestone badges: award Day 7 / 14 / 25 if this submission crossed
            # the threshold. Wrapped in a try so a badge failure never breaks /submit.
            try:
                newly_awarded = await asyncio.to_thread(check_and_award_milestones, interaction.user.id)
            except Exception as e:
                logger.error(f"Milestone check failed for user {interaction.user.id}: {e}")
                newly_awarded = []

            # Contest detection: poll LC + CF for any new contests this user
            # attended inside the event window, record them, and award any
            # contest-category badges (participant / rating_climber).
            # The helper handles rate limiting, partial failures, and
            # idempotency internally and returns both the new contests and
            # any newly-awarded badge metadata.
            try:
                new_contests, contest_badges = await record_user_contests(interaction.user.id)
            except Exception as e:
                logger.error(f"Contest poll failed for {interaction.user.id}: {e}")
                new_contests, contest_badges = [], []

        embed = create_submission_embed(
            student_id, cp_result.get('name', 'User'), day, description, cp_result,
            discord_user_id=interaction.user.id,
        )

        # If we detected any new contests this run, surface them in the embed
        # so the user immediately sees the points they just earned.
        if new_contests:
            lc_count = sum(1 for c in new_contests if c.platform == "leetcode")
            cf_count = sum(1 for c in new_contests if c.platform == "codeforces")
            from db.contests import contest_points
            pts = contest_points()
            parts = []
            if lc_count:
                parts.append(f"{lc_count} LeetCode")
            if cf_count:
                parts.append(f"{cf_count} Codeforces")
            embed.add_field(
                name="⚡ Contests detected",
                value=f"{' + '.join(parts)}  →  **+{pts * len(new_contests)} pts**",
                inline=False,
            )

        if not is_legal_time:
            embed.color = discord.Color.orange()
            embed.add_field(name="⚠️ Late Submission", value="This submission was made outside the designated time window and has been marked as late.", inline=False)
            
        await interaction.followup.send(embed=embed)

        # Announce any newly-earned badges (assigns role + posts a gold embed).
        # Milestone + contest badges all flow through the same announcer so
        # the user gets a single celebratory stream of gold embeds.
        if "error" not in cp_result:
            await announce_badges(interaction, newly_awarded + contest_badges)

    @app_commands.command(name="edit_submission", description="Edit a previous daily CP progress submission")
    @is_watched_channel()
    async def edit_submission(self, interaction: discord.Interaction, student_id: str, day: int, new_description: str):
        await interaction.response.defer()

        # If there's a pending queue entry for this day, update its description
        # instead of hitting the (likely still down) API again.
        is_queued = await asyncio.to_thread(has_pending_entry, student_id, day)
        if is_queued:
            await asyncio.to_thread(update_queued_description, student_id, day, new_description)
            embed = discord.Embed(
                title=f"📝 Day {day} Queued Submission Updated",
                description=(
                    "Your queued submission's description has been updated.\n"
                    "It will be verified when the API recovers."
                ),
                color=discord.Color.yellow(),
            )
            await interaction.followup.send(embed=embed)
            return
        
        cp_result = await asyncio.to_thread(process_slash_submission, student_id, day)
        
        if "error" not in cp_result:
            await asyncio.to_thread(update_cp_log_by_day, student_id, day, new_description, datetime.now(timezone.utc))
            messages_edited_total.inc()
            
        embed = create_submission_embed(
            student_id, cp_result.get('name', 'User'), day, new_description, cp_result,
            discord_user_id=interaction.user.id,
        )
        embed.title = f"📝 Edited " + embed.title
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="delete_submission", description="Delete a previous daily CP progress submission")
    @is_watched_channel()
    async def delete_submission(self, interaction: discord.Interaction, student_id: str, day: int):
        await interaction.response.defer()
        
        await asyncio.to_thread(delete_cp_log, student_id, day)
        
        embed = discord.Embed(title=f"Day {day} Submission Deleted", color=discord.Color.red())
        embed.description = f"🗑️ The submission for Day {day} has been removed for student {student_id}."
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="status", description="Check CP progress status for a specific day")
    @is_watched_channel()
    async def status(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
        day: int | None = None
    ):
        await interaction.response.defer()

        target = user or interaction.user
        profile = await asyncio.to_thread(get_student_profile, target.id)
        if not profile:
            await interaction.followup.send(
                f"❌ {target.display_name} has not registered yet.",
                ephemeral=True,
            )
            return

        student_id = profile["stu_id"]

        if day is None:
            from utils.event_window import get_event_day_number
            day = get_event_day_number() or 1
        
        status_result = await asyncio.to_thread(get_user_status, student_id, day)
        
        if "error" in status_result:
            embed = discord.Embed(title=f"Day {day} Status Error", color=discord.Color.red())
            embed.description = f"❌ {status_result['error']}"
            await interaction.followup.send(embed=embed)
            return
            
        solved = status_result['solved_questions']
        total = status_result['total_questions']
        day_questions = status_result['day_questions']
        
        color = discord.Color.green() if len(solved) == total else (discord.Color.gold() if len(solved) > 0 else discord.Color.red())
        
        embed = discord.Embed(title=f"Day {day} Status", color=color)
        embed.add_field(name="Student ID", value=student_id, inline=True)
        embed.add_field(name="Progress", value=f"{len(solved)}/{total} Questions Solved", inline=True)
        
        questions_status = ""
        for q in day_questions:
            if q.startswith("LC"): q_id = q[3:]
            elif q.startswith("CF"): q_id = q[3:]
            else: q_id = q
            status_emoji = "✅" if (q_id in solved or q in solved) else "❌"
            link = make_question_link(q)
            if link:
                questions_status += f"{status_emoji} [{q}]({link})\n"
            else:
                questions_status += f"{status_emoji} {q}\n"
        
        embed.add_field(name="Questions", value=questions_status, inline=False)
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(SubmissionsCog(bot))
