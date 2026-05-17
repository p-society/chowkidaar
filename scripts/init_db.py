import sys
import os

# Add parent directory to path so we can import db
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import psycopg2
from db.db import connect_to_database

def init_db():
    conn = connect_to_database()
    if not conn:
        print("Failed to connect")
        return
        
    try:
        cur = conn.cursor()

        # Create student_list_2024
        cur.execute("""
        CREATE TABLE IF NOT EXISTS student_list_2024 (
            stu_id VARCHAR(50) PRIMARY KEY,
            name VARCHAR(255),
            lc_handle VARCHAR(100),
            cf_handle VARCHAR(100),
            q1 TEXT[] DEFAULT '{}',
            q2 TEXT[] DEFAULT '{}',
            q3 TEXT[] DEFAULT '{}',
            all_solved TEXT[] DEFAULT '{}',
            is_late BOOLEAN DEFAULT FALSE,
            total_solved INTEGER DEFAULT 0
        );
        """)
        
        # Create participation_logs
        cur.execute("""
        CREATE TABLE IF NOT EXISTS participation_logs (
            id SERIAL PRIMARY KEY,
            sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT NULL,
            deleted_at TIMESTAMP DEFAULT NULL,
            message TEXT,
            discord_user_id BIGINT,
            discord_message_id BIGINT,
            in_text_valid INT DEFAULT -1
        );
        """)
        
        # Create day_brackets
        cur.execute("""
        CREATE TABLE IF NOT EXISTS day_brackets (
            day VARCHAR(10) PRIMARY KEY,
            initial_time TIMESTAMP,
            final_time TIMESTAMP
        );
        """)
        
        conn.commit()
        print("Successfully created database tables!")
        
    except Exception as e:
        print("Error:", e)
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    init_db()
