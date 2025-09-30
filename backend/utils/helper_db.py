import base64, json, sqlite3
from datetime import datetime
from typing import List, Optional
from pathlib import Path

DB_PATH = "interactions.db"

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS interactions (
        pair_id TEXT NOT NULL,
        rating INTEGER,
        seen INTEGER NOT NULL DEFAULT 0,
        starred INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (pair_id)
    )
    """)
    con.commit()
    con.close()

init_db()

def upsert_interaction(pair_id: str, rating: Optional[int], 
                       seen: Optional[bool], starred: Optional[bool]):
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT * FROM interactions WHERE pair_id=?", (pair_id))
    row = cur.fetchone()
    # merge with existing
    if row:
        rating_val  = rating  if rating  is not None else row["rating"]
        seen_val    = int(seen) if seen is not None else row["seen"]
        starred_val = int(starred) if starred is not None else row["starred"]
    else:
        rating_val  = rating
        seen_val    = int(seen) if seen is not None else 0
        starred_val = int(starred) if starred is not None else 0

    cur.execute("""
        INSERT INTO interactions (pair_id, rating, seen, starred, updated_at)
        VALUES (?,?,?,?,?)
        ON CONFLICT(pair_id) DO UPDATE SET
            rating=excluded.rating,
            seen=excluded.seen,
            starred=excluded.starred,
            updated_at=excluded.updated_at
    """, (pair_id, rating_val, seen_val, starred_val, datetime.utcnow().isoformat()))
    con.commit()
    con.close()

def fetch_interactions_map(pair_ids: List[str]):
    """Return {pair_id: {rating, seen, starred}} for given ids."""
    if not pair_ids:
        return {}
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    qmarks = ",".join("?" for _ in pair_ids)
    cur.execute(f"""
        SELECT pair_id, rating, seen, starred
        FROM interactions
        WHERE pair_id IN ({qmarks})
    """, (pair_ids))
    out = {r["pair_id"]: {"rating": r["rating"], "seen": bool(r["seen"]), "starred": bool(r["starred"])} for r in cur.fetchall()}
    con.close()
    return out

def b64enc(d: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(d).encode()).decode()

def b64dec(s: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(s.encode()).decode())

def make_pair_id(uuid_a: str, uuid_b: str) -> str:
    # stable id for a pair; order doesn’t really matter—keep current left/right
    return f"{uuid_a}__{uuid_b}"