import sqlite3
import pandas as pd
import os

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def load_file_to_db(uploaded_file) -> tuple[str, str, list[str]]:
    """
    Accepts CSV or XLSX files.
    Saves as SQLite DB in /data.
    Returns (db_path, table_name, columns).
    """
    filename = uploaded_file.name
    ext = filename.rsplit(".", 1)[-1].lower()

    # Read file based on extension
    if ext == "csv":
        df = pd.read_csv(uploaded_file)
    elif ext in ("xlsx", "xls"):
        df = pd.read_excel(uploaded_file)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    # Clean column names
    df.columns = [
        col.strip().replace(" ", "_").replace("-", "_").replace("(", "").replace(")", "")
        for col in df.columns
    ]

    # Use filename as table name
    table_name = filename.rsplit(".", 1)[0].replace(" ", "_").replace("-", "_").lower()
    db_path = os.path.join(DATA_DIR, f"{table_name}.db")

    con = sqlite3.connect(db_path)
    try:
        df.to_sql(table_name, con, if_exists="replace", index=False)
    finally:
        con.close()

    return db_path, table_name, df.columns.tolist()


def get_db_info(db_path: str) -> dict:
    """Returns table names and row counts."""
    con = sqlite3.connect(db_path)
    try:
        cursor = con.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall() if not r[0].startswith("sqlite_")]
        info = {}
        for table in tables:
            cursor.execute(f'SELECT COUNT(*) FROM "{table}"')
            info[table] = cursor.fetchone()[0]
        return info
    finally:
        con.close()