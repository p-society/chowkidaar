import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import sys
from loguru import logger
from jinja2 import Environment, FileSystemLoader
import schedule
import time
from get_environment import LoadEnv


def render_template(template_name, context):
    env = Environment(loader=FileSystemLoader('./templates/mail'))
    template = env.get_template(template_name)
    return template.render(context)

def send_email(subject, body, to_email, from_email="saswat.pb03@gmail.com", password=LoadEnv().get('GMAIL_APP_PASSWORD')):
    try:
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'html'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_email, password)
        server.sendmail(from_email, to_email, msg.as_string())
        server.quit()
        logger.info(f"Email sent to {to_email}")
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        sys.exit(1)



# def send_streak_reminder(to_email):
#     subject = "Don't Break Your Streak!"
#     body = "You're doing great! Remember to keep working and posting to maintain your streak."
#     send_email(subject, body, to_email)

# def send_daily_reminder(to_email, time_of_day):
#     if time_of_day == "morning":
#         subject = "Good Morning! Here's Your Daily Reminder"
#         body = "Start your day with a fresh mind and remember to work on your tasks."
#     elif time_of_day == "evening":
#         subject = "Last Hour to Submit!"
#         body = "The day is almost over. Make sure to submit your work before the day ends."
#     send_email(subject, body, to_email)

# def send_nomination_email(to_email, nominator_name):
#     subject = "You've Been Nominated!"
#     body = f"{nominator_name} has nominated you to participate. Join in and show your skills!"
#     send_email(subject, body, to_email)

# def job_morning_reminder():
#     users = get_user_emails()  # Define this function to fetch user emails
#     for user in users:
#         send_daily_reminder(user, "morning")

# def job_evening_reminder():
#     users = get_user_emails()  # Define this function to fetch user emails
#     for user in users:
#         send_daily_reminder(user, "evening")

# # Schedule the reminders
# schedule.every().day.at("08:00").do(job_morning_reminder)
# schedule.every().day.at("17:00").do(job_evening_reminder)

# while True:
#     schedule.run_pending()
#     time.sleep(1)

if __name__ == "__main__":
    test_body= render_template("streak_encouragement.html", context={"streak_count": 6})
    send_email("Test Subject", test_body, "b122103@iiit-bh.ac.in")