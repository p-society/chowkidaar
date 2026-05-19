import io
from os import times
import discord
from discord import app_commands
from config import DISCORD_TOKEN, WATCHED_CHANNEL_ID
from discord.ext import commands
from db.db import save_log, update_log, delete_log, flag_late, register_user, delete_cp_log, get_registered_name, get_student_profile
from db.badges import (
    check_and_award_milestones,
    list_user_badges,
    get_top_badge_emoji,
    format_name_with_badge,
    count_distinct_submission_days,
    current_streak,
)
from utils.card_generator import CardData, render_card
from utils.event_window import get_event_window
from utils.permissions import is_admin
from utils.time_check import can_send_message, is_in_time_bracket
from prometheus_client import Counter , Gauge, start_http_server
import logging as logger
from db.slash_commands_cp import process_slash_submission, get_user_status
from daily_resources.daily_questions import DailyQuestionScheduler, get_start_date  # Add this import
from daily_resources.dev_resources import DevResourcesScheduler  
from datetime import datetime, timezone

intents = discord.Intents.default()
intents.messages = True  # Ensure the bot can read messages
intents.message_content = True  # Add this line if you need access to message content
bot = commands.Bot(command_prefix="!", intents=intents)
bot.activity = discord.Activity(type=discord.ActivityType.watching, name="for message updates")

message_new_attempts_total= Counter('discord_messages_new_attempts_total', 'Total number of new messages received')
message_new_edits_total= Counter('discord_messages_new_edit_attempts_total', 'Total number of patch request received')

messages_sent_total = Counter('discord_messages_sent_total', 'Total number of messages saved in DB')
messages_edited_total = Counter('discord_messages_edited_total', 'Total number of messages patched in DB')
messages_deleted_total = Counter('discord_messages_deleted_total', 'Total number of messages deleted in DB')

errors_encountered_total = Counter('errors_encountered_total','Total Errors Encountered during bot"s processing of messages')

start_http_server(8000) 

def is_watched_channel():
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.channel_id == WATCHED_CHANNEL_ID
    return app_commands.check(predicate)

@bot.tree.command(name="register", description="Register your CP handles")
@is_watched_channel()
async def register(interaction: discord.Interaction, student_id: str, name: str, leetcode_handle: str, codeforces_handle: str):
    # Capture the caller's Discord ID so we can link stu_id <-> discord later
    # (used for badges, contest points, etc.).
    success = register_user(
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


def create_submission_embed(user_id, name, day, description, cp_result, discord_user_id=None):
    if "error" in cp_result:
        embed = discord.Embed(title=f"Day {day} Submission Error", color=discord.Color.red())
        embed.description = f"❌ {cp_result['error']}"
        return embed

    solved = cp_result['solved_questions']
    total = cp_result['total_questions']
    day_questions = cp_result['day_questions']

    color = discord.Color.green() if len(solved) == total else (discord.Color.gold() if len(solved) > 0 else discord.Color.red())

    # If we know the Discord user, prepend their top-badge emoji to the name.
    display_name = format_name_with_badge(discord_user_id, name) if discord_user_id else name
    embed = discord.Embed(title=f"Day {day} Submission: {display_name}", color=color)
    embed.add_field(name="Student ID", value=user_id, inline=True)
    embed.add_field(name="Progress", value=f"{len(solved)}/{total} Questions Solved", inline=True)
    
    questions_status = ""
    for q in day_questions:
        if q.startswith("LC"): q_id = q[3:]
        elif q.startswith("CF"): q_id = q[3:]
        else: q_id = q
        status_emoji = "✅" if q_id in solved else "❌"
        questions_status += f"{status_emoji} {q}\n"
    
    embed.add_field(name="Questions", value=questions_status, inline=False)
    
    if description:
        embed.add_field(name="Today's Work", value=description, inline=False)
        
    return embed

@bot.tree.command(name="submit", description="Submit your daily CP progress")
@is_watched_channel()
async def submit(interaction: discord.Interaction, student_id: str, day: int, description: str):
    await interaction.response.defer()
    
    # Process CP submissions
    cp_result = process_slash_submission(student_id, day)
    
    if "error" not in cp_result:
        # Time bracket check
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
    await interaction.followup.send(embed=embed)

    # Announce any newly-earned badges (assigns role + posts a gold embed).
    if "error" not in cp_result:
        await announce_badges(interaction, newly_awarded)

@bot.tree.command(name="edit_submission", description="Edit a previous daily CP progress submission")
@is_watched_channel()
async def edit_submission(interaction: discord.Interaction, student_id: str, day: int, new_description: str):
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

@bot.tree.command(name="delete_submission", description="Delete a previous daily CP progress submission")
@is_watched_channel()
async def delete_submission(interaction: discord.Interaction, student_id: str, day: int):
    await interaction.response.defer()
    
    delete_cp_log(student_id, day)
    
    embed = discord.Embed(title=f"Day {day} Submission Deleted", color=discord.Color.red())
    embed.description = f"🗑️ The submission for Day {day} has been removed for student {student_id}."
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="status", description="Check your CP progress status for a specific day")
@is_watched_channel()
async def status(interaction: discord.Interaction, student_id: str, day: int):
    await interaction.response.defer()
    
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
        status_emoji = "✅" if q_id in solved else "❌"
        questions_status += f"{status_emoji} {q}\n"
    
    embed.add_field(name="Questions", value=questions_status, inline=False)
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="badges", description="Show earned badges for yourself or another user")
@is_watched_channel()
async def badges(interaction: discord.Interaction, user: discord.Member | None = None):
    target = user or interaction.user
    rows = list_user_badges(target.id)

    # Prefer the registered name from student_list_2024; fall back to the
    # Discord display name only if the user hasn't registered yet.
    display = get_registered_name(target.id) or target.display_name

    embed = discord.Embed(
        title=f"🏆 Badges — {format_name_with_badge(target.id, display)}",
        color=discord.Color.gold() if rows else discord.Color.light_gray(),
    )
    if not rows:
        embed.description = "No badges yet. Keep submitting!"
    else:
        for b in rows:
            awarded = b["awarded_at"].strftime("%Y-%m-%d")
            embed.add_field(
                name=f"{b['name']}  ·  {b['category']}",
                value=f"{b['description']}\n*awarded {awarded}*",
                inline=False,
            )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="sync_badges", description="Recompute and award any milestone badges you've earned")
@is_watched_channel()
async def sync_badges(interaction: discord.Interaction, user: discord.Member | None = None):
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
    try:
        newly_awarded = check_and_award_milestones(target.id)
    except Exception as e:
        logger.error(f"sync_badges failed for {target.id}: {e}")
        await interaction.followup.send(f"❌ Sync failed: {e}", ephemeral=True)
        return

    if not newly_awarded:
        target_name = get_registered_name(target.id) or target.display_name
        await interaction.followup.send(
            f"✅ {format_name_with_badge(target.id, target_name)} is already up to date — no new badges to award.",
            ephemeral=True,
        )
        return

    # Re-use the announce helper, but it expects to followup on `interaction`,
    # which is fine since we deferred. It also handles role assignment.
    fake_interaction_user = interaction  # announce uses interaction.user.mention
    # If admin synced for another user, pretend "user" was them for the mention.
    # Simplest: just send embeds directly here.
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


@bot.tree.command(name="card", description="Generate a shareable progress card (Instagram-ready)")
@is_watched_channel()
async def card(interaction: discord.Interaction, user: discord.Member | None = None):
    """
    Build a 1080x1920 PNG summarizing the user's progress in the event.
    Anyone can run /card on themselves. Pass @user to view someone else's card.
    """
    target = user or interaction.user
    await interaction.response.defer()

    # ── Pull data from the DB ────────────────────────────────────────────
    profile = get_student_profile(target.id)
    if not profile:
        await interaction.followup.send(
            f"❌ {target.display_name} hasn't registered yet (or hasn't re-registered since "
            f"we started capturing Discord IDs). Ask them to run `/register` once.",
            ephemeral=True,
        )
        return

    start_utc, end_utc = get_event_window()
    day_progress = count_distinct_submission_days(target.id, start_utc, end_utc)
    streak = current_streak(target.id)

    # Earned badges → list of emojis ordered by display_priority (already sorted
    # via list_user_badges' awarded_at ordering; we re-sort by priority desc).
    badge_rows = list_user_badges(target.id)
    badge_rows_sorted = sorted(
        [b for b in badge_rows if b.get("description") is not None],
        key=lambda b: -(b.get("display_priority", 0) if isinstance(b, dict) else 0),
    )
    # We didn't pull display_priority + emoji in list_user_badges; refetch them.
    from db.db import connect_to_database
    badge_emojis: list[str] = []
    conn = connect_to_database()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT b.emoji
                    FROM user_badges ub
                    JOIN badges b ON b.key = ub.badge_key
                    WHERE ub.discord_user_id = %s
                      AND b.emoji IS NOT NULL
                    ORDER BY b.display_priority ASC
                    """,
                    (target.id,),
                )
                badge_emojis = [r[0] for r in cur.fetchall()]
        finally:
            conn.close()

    # ── Fetch the user's Discord avatar as PNG bytes ─────────────────────
    avatar_bytes: bytes | None = None
    try:
        # `display_avatar` falls back to the default avatar when none is set.
        asset = target.display_avatar.with_size(512).with_format("png")
        avatar_bytes = await asset.read()
    except Exception as e:
        logger.error(f"Failed to download avatar for {target.id}: {e}")

    # ── Render the card ──────────────────────────────────────────────────
    data = CardData(
        name=profile["name"],
        student_id=profile["stu_id"],
        day_progress=day_progress,
        streak=streak,
        total_solved=profile["total_solved"],
        badge_emojis=badge_emojis,
        avatar_png_bytes=avatar_bytes,
    )

    try:
        png_bytes = render_card(data)
    except Exception as e:
        logger.error(f"Card render failed for {target.id}: {e}")
        await interaction.followup.send(f"❌ Card render failed: {e}", ephemeral=True)
        return

    # ── Send as Discord attachment ───────────────────────────────────────
    filename = f"chowkidaar_card_{profile['stu_id']}.png"
    file = discord.File(io.BytesIO(png_bytes), filename=filename)
    await interaction.followup.send(
        content=f"Here's your card, {target.mention} — long-press to save, then share on Instagram.",
        file=file,
    )


@bot.tree.command(name="help", description="List all available commands")
@is_watched_channel()
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="Chowkidaar Bot Commands", color=discord.Color.blue())
    embed.description = "Here are all the available slash commands:"

    embed.add_field(name="📝 `/register`", value="Register your CP handles. \n`student_id`, `name`, `leetcode`, `codeforces`", inline=False)
    embed.add_field(name="🚀 `/submit`", value="Submit your daily CP progress. \n`student_id`, `day`, `description`", inline=False)
    embed.add_field(name="✏️ `/edit_submission`", value="Edit a previous daily CP progress submission. \n`student_id`, `day`, `new_description`", inline=False)
    embed.add_field(name="🗑️ `/delete_submission`", value="Delete a previous daily CP progress submission. \n`student_id`, `day`", inline=False)
    embed.add_field(name="📊 `/status`", value="Check your CP progress status for a specific day. \n`student_id`, `day`", inline=False)
    embed.add_field(name="🏆 `/badges`", value="Show earned badges for yourself or another user. \n`user` (optional)", inline=False)
    embed.add_field(name="🪪 `/card`", value="Generate a shareable progress card (Instagram-ready). \n`user` (optional)", inline=False)
    embed.add_field(name="🔁 `/sync_badges`", value="Recompute milestone badges. Admins can target another user. \n`user` (optional)", inline=False)
    embed.add_field(name="❓ `/help`", value="List all available commands.", inline=False)

    await interaction.response.send_message(embed=embed)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        await interaction.response.send_message("❌ This command can only be used in the designated progress channel.", ephemeral=True)
    else:
        logger.error(f"App command error: {error}")
        if not interaction.response.is_done():
            await interaction.response.send_message(f"❌ An error occurred: {error}", ephemeral=True)


@bot.event
async def on_message(message):
    message_new_attempts_total.inc()
    if message.author == bot.user:
        return

    # No text processing is required anymore for CP tracking; everything is handled via slash commands.
    # If other traditional commands exist, they would be processed here.
    await bot.process_commands(message)

@bot.event
async def on_ready():
    logger.info(f"Bot is ready. Logged in as {bot.user}", extra={"tags": {"event": "on_ready"}})
    print(f"Bot is ready. Logged in as {bot.user}")
    
    # Start the daily question scheduler
    start_date = get_start_date()  # Import this from daily_questions
    question_scheduler = DailyQuestionScheduler(bot, WATCHED_CHANNEL_ID)
    dev_resources_scheduler = DevResourcesScheduler(bot, WATCHED_CHANNEL_ID, start_date)
    
    logger.info("Daily schedulers started", extra={"tags": {"event": "scheduler_start"}})
    
    # Sync slash commands. If DEV_GUILD_ID is set (in .env.local), we sync to
    # that guild only — propagation is instant. Otherwise we do a global sync,
    # which can take up to an hour to show up in Discord clients.
    try:
        from os import getenv
        dev_guild_id = getenv("DEV_GUILD_ID")
        if dev_guild_id:
            guild = discord.Object(id=int(dev_guild_id))
            # Mirror all commands (registered globally via decorators) into the guild.
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
            print(f"Synced {len(synced)} command(s) to guild {dev_guild_id} (instant)")
            logger.info(f"Synced {len(synced)} command(s) to guild {dev_guild_id}")
            # Then clear global commands so they don't appear duplicated alongside
            # the guild-scoped copies. Idempotent — safe to call on every boot.
            bot.tree.clear_commands(guild=None)
            await bot.tree.sync()
            print("Cleared global commands (so they don't duplicate the guild copies)")
        else:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} command(s) globally (may take up to 1h)")
            logger.info(f"Synced {len(synced)} command(s) globally")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
        print(f"Failed to sync commands: {e}")
    
bot.run(DISCORD_TOKEN)
