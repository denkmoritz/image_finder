import base64, json, sqlite3
from datetime import datetime
from typing import List, Optional
from pathlib import Path
DB_PATH = "liked.db"
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    # Create table if it doesn't exist
    cur.execute("""
        CREATE TABLE IF NOT EXISTS liked (
            uuid_1 TEXT,
            uuid_2 TEXT,
            orig_id_1 INTEGER,
            orig_id_2 INTEGER,
            distance FLOAT
        )
    """)
    
    # Try to add created_at column if it doesn't exist
    try:
        # SQLite doesn't allow non-constant defaults in ALTER TABLE
        # So we add it without a default, then update existing rows
        cur.execute("ALTER TABLE liked ADD COLUMN created_at TIMESTAMP")
        # Set a value for existing rows
        cur.execute("UPDATE liked SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        con.commit()
        print("Added created_at column")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("created_at column already exists")
        else:
            raise
    
    con.close()
init_db()