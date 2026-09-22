import sqlite3
import pandas as pd

# 1. Load your CSV data into a DataFrame
csv_file = "data/store.csv"
df = pd.read_csv(csv_file)

# 2. Connect to SQLite database (creates the file if it doesn't exist)
db_file = "sales.db"
conn = sqlite3.connect(db_file)

# 3. Load the data into a new SQLite table
# Change 'my_table' to whatever you want to name your table
df.to_sql("sales", conn, if_exists="replace", index=False)

cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]

print("Dialect: sqlite")
print(f"Available tables: {tables}")

cursor.execute("SELECT * FROM sales LIMIT 5;")
print(f"Sample output: {cursor.fetchall()}")

# Close the database connection
conn.close()
print("Data loaded successfully via Pandas!")


