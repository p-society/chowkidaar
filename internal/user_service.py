import psycopg2
import uuid
from datetime import datetime

class User_Service:
    def save_to_db(self, data: dict):
        try:
            print("hi")
            # Connect to the PostgreSQL database
            conn = psycopg2.connect(
            database="chowkidaar",
            user="postgres",
            host="127.0.0.1",
            password="admin",
            port=5432,
            )
            cursor = conn.cursor()

            # Prepare the SQL INSERT statement dynamically
            sql = """INSERT INTO users (id, college_id, discord_username, discriminator, avatar_url, 
                     account_created_at, display_name, branch, email) 
                     VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                     RETURNING id"""
            
            # Generating unique ID for the user
            user_id = str(uuid.uuid4())

            # Format data for insertion
            data_to_insert = (
                user_id,
                data["college_id"],
                data["discord_username"],
                data["discriminator"],
                data["avatar_url"],
                datetime.now(),
                data["display_name"],
                data["branch"],
                data["email"]
            )
            print(data_to_insert,"data_to_insert")
            # Execute the INSERT statement with data from the dictionary
            cursor.execute(sql, data_to_insert)
            inserted_id = cursor.fetchone()[0]
            # Commit the transaction
            conn.commit()
            print("Data inserted successfully!")
            
            if conn:
                cursor.close()
                conn.close()
            return inserted_id
        except (Exception, psycopg2.Error) as error:
            print("Error while inserting data into PostgreSQL:", error)