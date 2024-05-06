import psycopg2

def migrate_chowkidaar_models():
    try:
        conn = psycopg2.connect(
            database="chowkidaar",
            user="postgres",
            host="127.0.0.1",
            password="admin",
            port=5432,
        )

        cur = conn.cursor()

        create_participation_logs_table = """
CREATE TABLE participation_logs (
    id TEXT PRIMARY KEY,
    sent_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE,
    deleted_at TIMESTAMP WITH TIME ZONE,
    message VARCHAR(200) NOT NULL,
    user_id TEXT REFERENCES users (id) NOT NULL -- Correct syntax for foreign key constraint
);
"""
        
        create_users_table = """
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    college_id VARCHAR(7) NOT NULL,
    discord_username VARCHAR(50) NOT NULL,
    discriminator VARCHAR(50) NOT NULL,
    avatar_url VARCHAR(200) NOT NULL,
    account_created_at TIMESTAMP WITH TIME ZONE,
    display_name VARCHAR(50) NOT NULL,
    branch VARCHAR(10) NOT NULL,
    email VARCHAR(50) UNIQUE NOT NULL -- Changed VARCHAR(20) to VARCHAR(50) for email length
);
"""
        
        create_change_log = '''
        '''
        # 1 -> discord_username -> change ->
        # g ->id1
        # w ->id2
        # e ->id3
        cur.execute(create_users_table)
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