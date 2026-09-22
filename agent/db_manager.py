import sqlite3
import pandas as pd
import os

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

def load_file_to_db(uploaded_file) -> tuple[str, str, list[str]]:
    filename = uploaded_file.name
    ext = filename.rsplit(".", 1)[-1].lower()
    base_name = filename.rsplit(".", 1)[0].replace(" ", "_").replace("-", "_").lower()
    db_path = os.path.join(DATA_DIR, f"{base_name}.db")

    all_tables = []
    all_columns = {}

    if ext == "csv":
        df = pd.read_csv(uploaded_file)
        df.columns = [clean_col(col) for col in df.columns]
        table_name = base_name
        save_df_to_db(df, table_name, db_path)
        all_tables.append(table_name)
        all_columns[table_name] = df.columns.tolist()

    elif ext in ("xlsx", "xls"):
        # Read ALL sheets
        sheets = pd.read_excel(uploaded_file, sheet_name=None)  # None = all sheets
        for sheet_name, df in sheets.items():
            if df.empty:
                continue
            # Clean sheet name for use as table name
            table_name = sheet_name.strip().replace(" ", "_").replace("-", "_").lower()
            df.columns = [clean_col(col) for col in df.columns]
            # Drop columns that are entirely empty
            df = df.dropna(axis=1, how="all")
            # Drop rows that are entirely empty
            df = df.dropna(axis=0, how="all")
            if df.empty:
                continue
            save_df_to_db(df, table_name, db_path)
            all_tables.append(table_name)
            all_columns[table_name] = df.columns.tolist()
    else:
        raise ValueError(f"Unsupported file type: {ext}")

    return db_path, all_tables, all_columns


def clean_col(col: str) -> str:
    """Clean column names — remove spaces, special chars."""
    import re
    col = str(col).strip()
    col = re.sub(r"[^a-zA-Z0-9_]", "_", col)
    col = re.sub(r"_+", "_", col)           # remove double underscores
    col = col.strip("_")
    return col


def save_df_to_db(df: pd.DataFrame, table_name: str, db_path: str):
    """Save a dataframe as a table in SQLite."""
    con = sqlite3.connect(db_path)
    try:
        df.to_sql(table_name, con, if_exists="replace", index=False)
    finally:
        con.close()


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