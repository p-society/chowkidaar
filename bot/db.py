import psycopg2
from config import DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD, DATABASE_HOST

def connect_to_database():
    try:
        conn = psycopg2.connect(
            dbname=DATABASE_NAME,
            user=DATABASE_USER,
            password=DATABASE_PASSWORD,
            host=DATABASE_HOST
        )
        print("Connection to the database was successful")
        return conn
    except psycopg2.Error as e:
        print(f"Error connecting to the database: {e}")
        return None
    
def save_log(conn, message, discord_user_id, discord_message_id, sent_at, in_text_valid=-1):
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO participation_logs (
                message, discord_user_id, discord_message_id, sent_at, in_text_valid
            ) VALUES (%s, %s, %s, %s, %s)
            """,
            (message, discord_user_id, discord_message_id, sent_at, in_text_valid)
        )
        conn.commit()
    except psycopg2.Error as e:
        print(f"Error occurred while saving log: {e}")
        conn.rollback()  # Rollback the transaction if there is any error
    finally:
        cur.close()




if __name__ == "__main__":
    connection = connect_to_database()
    if connection:
        cursor = connection.cursor()
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()
        print(f"Database version: {db_version}")
        
        cursor.close()
        connection.close()
