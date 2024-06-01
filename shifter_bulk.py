import pandas as pd
import psycopg2
from psycopg2 import Error
from config import DATABASE_NAME, DATABASE_USER, DATABASE_PASSWORD, DATABASE_HOST
from db import connect_to_database

def upload_csv_to_pg(csv_file, table_name):
    try:
        # Connect to the PostgreSQL database
        conn = connect_to_database()
        
        # Create a cursor object using the connection
        cursor = conn.cursor()
        
        create_table_query = """
            CREATE TABLE IF NOT EXISTS student_list_2023 (
              sl INT PRIMARY KEY,
              student_id VARCHAR(10) NOT NULL,
              name VARCHAR(255) NOT NULL,
              gender VARCHAR(10) NOT NULL,
              branch VARCHAR(50) NOT NULL
            );
        """

        try:
            cursor.execute(create_table_query)
            conn.commit()  
            print("Table created successfully!")
        except Exception as e:
            print("Error:", e)
            conn.rollback()  

        # Read the CSV file into a pandas DataFrame
        df = pd.read_csv(csv_file)

        # Convert DataFrame to list of tuples
        data = [tuple(row) for row in df.to_numpy()]

        # Generate the SQL INSERT statement
        cols = ', '.join(df.columns)
        placeholders = ', '.join(['%s'] * len(df.columns))
        sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"

        # Execute the SQL statement to insert data into the table
        cursor.executemany(sql, data)

        # Commit the transaction
        conn.commit()
        
        print("Data uploaded successfully")

    except (Exception, Error) as e:
        print(f"Error uploading data to PostgreSQL: {e}")

    finally:
        # Close the cursor and connection
        if conn:
            cursor.close()
            conn.close()


csv_file = "./list.csv"

table_name = "student_list_2023"

upload_csv_to_pg(csv_file, table_name)
