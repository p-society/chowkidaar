import psycopg2
from db import connect_to_database


def migrate_chowkidaar_models():
    try:
        conn = connect_to_database()
        cur = conn.cursor()

        create_participation_logs_table = """
CREATE TABLE participation_logs (
    id SERIAL PRIMARY KEY,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT NULL,
    deleted_at TIMESTAMP DEFAULT NULL,
    message TEXT NOT NULL,
    discord_user_id BIGINT NOT NULL,
    discord_message_id BIGINT NOT NULL,
    in_text_valid INT DEFAULT -1
);
"""

        create_users_table = """
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    college_id VARCHAR(10) NOT NULL,
    discord_username VARCHAR(50) NOT NULL,
    discriminator VARCHAR(50) NOT NULL,
    avatar_url VARCHAR(200) NOT NULL,
    account_created_at TIMESTAMP WITH TIME ZONE,
    display_name VARCHAR(50) NOT NULL,
    branch VARCHAR(10) NOT NULL,
    email VARCHAR(50) UNIQUE NOT NULL -- Changed VARCHAR(20) to VARCHAR(50) for email length
);
"""

        create_change_log = """
        """
        # 1 -> discord_username -> change ->
        # g ->id1
        # w ->id2
        # e ->id3
        # cur.execute(create_users_table)
        cur.execute(create_participation_logs_table)

        conn.commit()
        print("Migration completed successfully!")

    except (Exception, psycopg2.Error) as error:
        print("Error while migrating tables:", error)

    finally:
        if conn:
            cur.close()
            conn.close()


migrate_chowkidaar_models()
