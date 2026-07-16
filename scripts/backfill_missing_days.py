import psycopg2
import sys
import os
import datetime

DB_URL = os.environ.get("NEON_DB_URL")

def insert_log(conn, did, target_date_str):
    cur = conn.cursor()
    # Create a synthetic timestamp around 20:00 UTC (1:30 AM IST) on the target date
    # so that it safely falls into the correct day's bracket.
    target_date = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").date()
    sent_at = datetime.datetime.combine(target_date, datetime.time(20, 0), tzinfo=datetime.timezone.utc)
    
    # Check if a log already exists for safety
    cur.execute("""
        SELECT 1 FROM participation_logs
        WHERE discord_user_id = %s 
          AND DATE((sent_at AT TIME ZONE 'UTC') - INTERVAL '16 hours 30 minutes') = %s
    """, (did, target_date_str))
    
    if cur.fetchone():
        print(f"Log already exists for {did} on {target_date_str}")
        return
        
    cur.execute("""
        INSERT INTO participation_logs (
            message, discord_user_id, discord_message_id, sent_at, in_text_valid
        ) VALUES (
            %s, %s, %s, %s, %s
        )
    """, ("Admin Backfill", did, 1000000000000000000 + did, sent_at, 1))
    
    conn.commit()
    print(f"✅ Backfilled log for {did} on {target_date_str}")

def run():
    conn = psycopg2.connect(DB_URL)
    
    # Likhith
    insert_log(conn, 791891919390507019, "2026-06-24")
    # Mohit
    insert_log(conn, 1429548784412655748, "2026-06-20")
    # Yug
    insert_log(conn, 760506662863372309, "2026-06-01")
    
    conn.close()

if __name__ == "__main__":
    run()
