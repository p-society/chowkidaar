import discord
from discord import app_commands
from discord.ext import commands
from datetime import datetime, timezone
import logging as logger

from db.db import save_log, update_log, delete_cp_log, get_student_profile
from db.badges import check_and_award_milestones, format_name_with_badge
from db.slash_commands_cp import process_slash_submission, get_user_status
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
        
        # Process CP submissions
        cp_result = process_slash_submission(student_id, day)
        
        is_legal_time = True
        if "error" not in cp_result:
            # Time bracket check
            from db.db import flag_late
            is_legal_time = is_in_time_bracket(day, datetime.now(timezone.utc))
            if not is_legal_time:
                flag_late(student_id)
                
            # Save log
            save_log(description, interaction.user.id, interaction.id, interaction.created_at, 1)
            messages_sent_total.inc()

            # Milestone badges: award Day 7 / 14 / 25 if this submission crossed
            # the threshold. Wrapped in a try so a badge failure never breaks /submit.
            try:
                newly_awarded = check_and_award_milestones(interaction.user.id)
            except Exception as e:
                logger.error(f"Milestone check failed for user {interaction.user.id}: {e}")
                newly_awarded = []

        embed = create_submission_embed(
            student_id, cp_result.get('name', 'User'), day, description, cp_result,
            discord_user_id=interaction.user.id,
        )
        
        if not is_legal_time:
            embed.color = discord.Color.orange()
            embed.add_field(name="⚠️ Late Submission", value="This submission was made outside the designated time window and has been marked as late.", inline=False)
            
        await interaction.followup.send(embed=embed)

        # Announce any newly-earned badges (assigns role + posts a gold embed).
        if "error" not in cp_result:
            await announce_badges(interaction, newly_awarded)

    @app_commands.command(name="edit_submission", description="Edit a previous daily CP progress submission")
    @is_watched_channel()
    async def edit_submission(self, interaction: discord.Interaction, student_id: str, day: int, new_description: str):
        await interaction.response.defer()
        
        cp_result = process_slash_submission(student_id, day)
        
        if "error" not in cp_result:
            update_log(interaction.id, new_description, 1, datetime.now(timezone.utc))
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
        
        delete_cp_log(student_id, day)
        
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
        profile = get_student_profile(target.id)
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
        
        status_result = get_user_status(student_id, day)
        
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
