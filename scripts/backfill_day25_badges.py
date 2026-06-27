import sys
import os
import asyncio

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.db import connect_to_database
from db.badges import check_and_award_milestones

async def run():
    conn = connect_to_database()
    cur = conn.cursor()
    
    # Get all users who have max_streak >= 25 now
    cur.execute("""
        WITH streaks AS (
            SELECT discord_user_id, COUNT(DISTINCT DATE((sent_at AT TIME ZONE 'UTC') - INTERVAL '16 hours 30 minutes')) as count
            FROM participation_logs 
            WHERE deleted_at IS NULL AND in_text_valid = 1
              AND sent_at >= '2026-06-01'::timestamp
              AND sent_at < '2026-06-26'::timestamp + INTERVAL '1 day'
            GROUP BY discord_user_id
        )
        SELECT discord_user_id FROM streaks WHERE count >= 25
    """)
    users = [row[0] for row in cur.fetchall()]
    
    print(f"Found {len(users)} users with 25+ streak.")
    for uid in users:
        awarded = check_and_award_milestones(uid)
        if awarded:
            print(f"Awarded badges {awarded} to {uid}")
            
    conn.close()

if __name__ == "__main__":
    asyncio.run(run())
