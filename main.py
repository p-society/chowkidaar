# Third party imports
from discord.ext import commands
import discord

# Local imports
from config import DISCORD_TOKEN
from config import WATCHED_CHANNEL_ID
from daily_resources.daily_questions import DailyQuestionScheduler
from daily_resources.daily_questions import get_start_date
from daily_resources.dev_resources import DevResourcesScheduler
from db.db import save_log
from db.db import check_intext_validity
from db.db import update_log
from db.db import delete_log
from db.db import flag_late
from db.mark_cp_logs import process_submissions
from prometheus_client import Counter
from prometheus_client import start_http_server
from utils.time_check import can_send_message
from utils.time_check import is_in_time_bracket
import logging as logger


# Setting up the bot and it's configuration.
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
bot.activity = discord.Activity(
    type=discord.ActivityType.watching, name="for message updates"
)

# Counter for all messages attempted. Includes the one missed in the DB.
message_new_attempts_total = Counter(
    "discord_messages_new_attempts_total", "Total number of new messages received"
)
message_new_edits_total = Counter(
    "discord_messages_new_edit_attempts_total", "Total number of patch request received"
)

# Counter for all messages sent and present in the DB.
messages_sent_total = Counter(
    "discord_messages_sent_total", "Total number of messages saved in DB"
)
messages_edited_total = Counter(
    "discord_messages_edited_total", "Total number of messages patched in DB"
)
messages_deleted_total = Counter(
    "discord_messages_deleted_total", "Total number of messages deleted in DB"
)

# Counter for total errors encountered.
errors_encountered_total = Counter(
    "errors_encountered_total",
    'Total Errors Encountered during bot"s processing of messages',
)

start_http_server(8000)


@bot.event
async def on_message(message):
    """
    Handles all incoming messages in the Discord server.

    This function is responsible for:
    - Ignoring messages from the bot, Arcane bot and a bunch of others .
    - Logging the receipt of every user message.
    - Determining if the message is a registration or a daily log submission.
    - End to end processing of submission messages as well as registration.
    - Saving valid messages and their metadata to the database.
    - Reacting to the message with emojis based on the outcome:
        📝 - Successful registration or registration required
        ✔  - Registration saved to database
        ✅ - Daily goal fully completed
        ⏳ - Partial completion of daily goal
        ❌ - No CP submissions found
        ⏰ - Submission was late
        🎊 - Valid message stored successfully
        👁️ - Message not saved due to timing/validation issues
        ⚠️ - Other errors during processing

    Args:
        message (discord.Message): The message object representing a user message from Discord.

    Raises:
        Logs exceptions if any occur during message processing and increments the error metric counter.

    Returns:
        None

    Metrics Tracked:
    - `message_new_attempts_total`: Incremented on each message received.
    - `messages_sent_total`: Incremented when a valid message is successfully stored.
    - `errors_encountered_total`: Incremented when any unhandled exception is caught.
    """
    message_new_attempts_total.inc()
    if message.author == bot.user:
        return

    if message.channel.id != WATCHED_CHANNEL_ID:
        return

    # Ignore arcane
    if message.author.id == 437808476106784770:
        return

    discord_user_id = message.author.id
    discord_message_id = message.id
    content = str(message.content)
    timestamp = message.created_at
    logger.info(
        f"Received Message from discord_user_id {discord_user_id}",
        extra={"tags": {"event": "on_message"}},
    )

    try:
        # Process CP submissions
        submission_result = process_submissions(content)

        # Handle registration message
        if (
            submission_result
            and "status" in submission_result
            and submission_result["status"] == "success"
            and "message" in submission_result
            and "registered" in submission_result["message"].lower()
        ):
            logger.info(f"User registration successful for {discord_user_id}.")
            logger.info(f"Added 📝 reaction for successful registration")
            await message.add_reaction("📝")

            # Save registration message to database without validity check
            save_log(
                content,
                discord_user_id,
                discord_message_id,
                timestamp,
                1,
            )
            logger.info(
                f"Registration message from {message.author.name} saved to the database.",
                extra={"tags": {"event": "on_message"}},
            )
            await message.add_reaction("✔")
            messages_sent_total.inc()

        # Handle daily log message
        if (
            submission_result
            and "status" in submission_result
            and submission_result["status"] == "success"
        ):
            is_legal_time = is_in_time_bracket(submission_result["day"], timestamp)
            in_text_valid = check_intext_validity(content)
            daily_goal_status = len(submission_result["solved_questions"]) / (
                submission_result["total_questions"]
            )

            if daily_goal_status == 1:
                logger.info(
                    f"CP submissions processed successfully for user {discord_user_id}.",
                    extra={"tags": {"event": "on_message"}},
                )
                logger.info(
                    f"{discord_user_id} has completed all the questions",
                    extra={"tags": {"event": "on_message"}},
                )
                await message.add_reaction("✅")
                logger.info(
                    f"Added ✅ reaction", extra={"tags": {"event": "on_message"}}
                )
            elif daily_goal_status < 1 and daily_goal_status != 0:
                logger.info(
                    f"CP submissions processed successfully for user {discord_user_id}.",
                    extra={"tags": {"event": "on_message"}},
                )
                logger.info(
                    f"{discord_user_id} has partially completed the questions",
                    extra={"tags": {"event": "on_message"}},
                )
                await message.add_reaction("⏳")
                logger.info(
                    f"Added ⏳ reaction", extra={"tags": {"event": "on_message"}}
                )
            elif daily_goal_status == 0:
                logger.info(
                    f"No CP submissions for user {discord_user_id}.",
                    extra={"tags": {"event": "on_message"}},
                )
                logger.info(
                    f"{discord_user_id} has no submissions",
                    extra={"tags": {"event": "on_message"}},
                )
                await message.add_reaction("❌")
                logger.info(
                    f"Added ❌ reaction", extra={"tags": {"event": "on_message"}}
                )

            if not is_legal_time:
                flag_late(submission_result["user_id"])
                logger.info(
                    f"CP submissions processed with late submission for user {discord_user_id}.",
                    extra={"tags": {"event": "on_message"}},
                )
                await message.add_reaction("⏰")
                logger.info(
                    f"Added ⏰ reaction", extra={"tags": {"event": "on_message"}}
                )

            # Check message validity and save to database only for daily logs
            if can_send_message(discord_user_id, timestamp, submission_result["day"]):
                logger.info(
                    f"discord_message_id :{discord_message_id} can be stored in DB.",
                    extra={"tags": {"event": "on_message"}},
                )
                save_log(
                    content,
                    discord_user_id,
                    discord_message_id,
                    timestamp,
                    in_text_valid,
                )
                logger.info(
                    f"Message from {message.author.name} saved to the database.",
                    extra={"tags": {"event": "on_message"}},
                )
                print(f"Message from {message.author.name} saved to the database.")
                await message.add_reaction("🎊")
                logger.info(
                    f"Reaction 🎊 added to discord_user_id: {discord_user_id} for message id:{ discord_message_id}  successfully.",
                    extra={"tags": {"event": "on_message"}},
                )
                messages_sent_total.inc()
            else:
                logger.warning(
                    f"Message from {message.author.name} could not be saved to the database.",
                    extra={"tags": {"event": "on_message"}},
                )
                print(
                    f"Message from {message.author.name} could not be saved to the database."
                )
                await message.add_reaction("👁️")
                logger.info(
                    f"Reaction 👁️ added to discord_user_id: {discord_user_id} for message id:{ discord_message_id}  successfully.",
                    extra={"tags": {"event": "on_message"}},
                )

        # Handle errors
        elif submission_result and "error" in submission_result:
            error_msg = submission_result["error"]
            logger.warning(
                f"CP processing error: {error_msg}",
                extra={"tags": {"event": "on_message"}},
            )

            # Different reactions for different types of errors
            if (
                "not registered" in error_msg.lower()
                or "handle not found" in error_msg.lower()
            ):
                await message.add_reaction("📝")  # Registration needed
                logger.info(
                    f"Added 📝 reaction for registration needed",
                    extra={"tags": {"event": "on_message"}},
                )
            else:
                await message.add_reaction("⚠️")  # Other errors
                logger.info(
                    f"Added ⚠️ reaction for other errors",
                    extra={"tags": {"event": "on_message"}},
                )

    except Exception as e:
        logger.error(
            f"Error processing message: {e}", extra={"tags": {"event": "on_message"}}
        )
        print(f"Error processing message: {e}")
        errors_encountered_total.inc()
    await bot.process_commands(message)


@bot.event
async def on_message_edit(old_message, new_message):
    message_new_edits_total.inc()
    if new_message.author == bot.user:
        return
    if new_message.channel.id != WATCHED_CHANNEL_ID:
        return
    # ignore arcane
    if new_message.author.id == 437808476106784770:
        return
    discord_user_id = new_message.author.id
    discord_message_id = new_message.id
    content = str(new_message.content)
    timestamp = new_message.created_at
    updated_at = new_message.edited_at
    in_text_valid = check_intext_validity(content)

    logger.info(
        f"Edit event from {discord_user_id} for message id: { discord_message_id} received.",
        extra={"tags": {"event": "on_message_edit"}},
    )
    try:
        # Process CP submissions for edited message
        submission_result = process_submissions(content)
        if submission_result and "error" not in submission_result:
            logger.info(
                f"CP submissions processed successfully for edited message from user {discord_user_id}",
                extra={"tags": {"event": "on_message_edit"}},
            )
            if submission_result["solved_questions"]:
                await new_message.add_reaction("✅")
                logger.info(
                    f"Added ✅ reaction for solved CP questions in edited message",
                    extra={"tags": {"event": "on_message_edit"}},
                )
        elif submission_result and "error" in submission_result:
            logger.warning(
                f"CP processing error in edited message: {submission_result['error']}",
                extra={"tags": {"event": "on_message_edit"}},
            )

        if is_in_time_bracket(submission_result["day"], timestamp) and update_log(
            discord_message_id, content, in_text_valid, updated_at
        ):
            logger.info(
                f"Edit event from discord_user_id:{discord_user_id} for message id:{ discord_message_id} successfully patched in DB.",
                extra={"tags": {"event": "on_message_edit"}},
            )

            await new_message.add_reaction("🛠️")
            logger.info(
                f"Reaction 🛠️ added to discord_user_id: {discord_user_id} for message id:{ discord_message_id}  successfully.",
                extra={"tags": {"event": "on_message_edit"}},
            )

            messages_edited_total.inc()
        else:
            logger.info(
                f"Edited message from {new_message.author.name} for message id:{ discord_message_id}  could not be saved to the database.",
                extra={"tags": {"event": "on_message_edit"}},
            )
            print(
                f"Edited message from {new_message.author.name} for message id:{ discord_message_id}  could not be saved to the database."
            )
            await new_message.add_reaction("👀")
            logger.warning(
                f"Reaction 👀 added to discord_user_id: {discord_user_id} for message id: {discord_message_id} successfully.",
                extra={"tags": {"event": "on_message_edit"}},
            )

    except Exception as e:
        logger.error(
            f"Error updating message in database: {e}",
            extra={"tags": {"event": "on_message_edit"}},
        )
        print(f"Error updating message in database: {e}")
        errors_encountered_total.inc()

    await bot.process_commands(new_message)


@bot.event
async def on_message_delete(message):
    if message.author == bot.user:
        return
    if message.channel.id != WATCHED_CHANNEL_ID:
        return
    # ignore arcane
    if message.author.id == 437808476106784770:
        return

    discord_message_id = message.id
    logger.info(
        f"Delete event for message id: {discord_message_id} received.",
        extra={"tags": {"event": "on_message_delete"}},
    )

    try:
        delete_log(discord_message_id)
        logger.info(
            f"Message with ID {discord_message_id} was marked deleted.",
            extra={"tags": {"event": "on_message_delete"}},
        )
        print(f"Message with ID {discord_message_id} was marked deleted.")
        messages_deleted_total.inc()
    except Exception as e:
        errors_encountered_total.inc()
        logger.error(f"Error deleting message from database: {e}")
        print(f"Error deleting message from database: {e}")
    await bot.process_commands(message)


@bot.event
async def on_ready():
    logger.info(
        f"Bot is ready. Logged in as {bot.user}", extra={"tags": {"event": "on_ready"}}
    )
    print(f"Bot is ready. Logged in as {bot.user}")

    # Start the daily question scheduler
    start_date = get_start_date()  # Import this from daily_questions
    question_scheduler = DailyQuestionScheduler(bot, WATCHED_CHANNEL_ID)
    dev_resources_scheduler = DevResourcesScheduler(bot, WATCHED_CHANNEL_ID, start_date)

    logger.info(
        "Daily schedulers started", extra={"tags": {"event": "scheduler_start"}}
    )


bot.run(DISCORD_TOKEN)
