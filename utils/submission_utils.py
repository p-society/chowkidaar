import re
import discord
from db.badges import format_name_with_badge

def make_question_link(q: str) -> str:
    if q.startswith("LC-") or q.startswith("LC"):
        q_id = q[3:] if q.startswith("LC-") else q[2:]
        return f"https://leetcode.com/problems/{q_id}/"
    elif q.startswith("CF-") or q.startswith("CF"):
        q_id = q[3:] if q.startswith("CF-") else q[2:]
        match = re.match(r"(\d+)([A-Z]\d*)", q_id)
        if match:
            contest_id = match.group(1)
            problem_index = match.group(2)
            return f"https://codeforces.com/problemset/problem/{contest_id}/{problem_index}"
        return "https://codeforces.com/problemset/"
    return ""

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
        status_emoji = "✅" if (q_id in solved or q in solved) else "❌"
        link = make_question_link(q)
        if link:
            questions_status += f"{status_emoji} [{q}]({link})\n"
        else:
            questions_status += f"{status_emoji} {q}\n"
    
    embed.add_field(name="Questions", value=questions_status, inline=False)
    
    if description:
        embed.add_field(name="Today's Work", value=description, inline=False)
        
    return embed
