#!/usr/bin/env python3
"""
Delete rows listed in delete_uuids.txt from the 'berlin' table.

- Reads one UUID per line from DELETE_LIST_PATH
- Uses utils.db.get_db_connection() (SQLAlchemy Engine)
- Deletes in chunks, inside a single transaction
"""

from __future__ import annotations
import os
from typing import List
from sqlalchemy import text, bindparam
from utils.db import get_db_connection

# -------- Config (no CLI args) --------
DELETE_LIST_PATH = "delete_uuids_by_quality.txt"   # one UUID per line
TABLE_NAME = "singapore"                   # target table
PK_COLUMN = "uuid"                      # primary key / column to match
CHUNK_SIZE = 1000                       # tune if needed
DO_COUNT_BEFORE = True                  # set False to skip pre-count
# --------------------------------------

def read_uuid_list(path: str) -> List[str]:
    if not os.path.isfile(path):
        raise FileNotFoundError(f"UUID list file not found: {path}")
    uuids: List[str] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip().strip('"').strip("'")
            if s:
                uuids.append(s)
    # de-duplicate while preserving order
    seen = set()
    out: List[str] = []
    for u in uuids:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

def chunked(seq: List[str], n: int):
    for i in range(0, len(seq), n):
        yield seq[i:i+n]

def main():
    uuids = read_uuid_list(DELETE_LIST_PATH)
    total_ids = len(uuids)
    if total_ids == 0:
        print(f"No UUIDs found in {DELETE_LIST_PATH}. Nothing to do.")
        return

    print(f"Loaded {total_ids} unique UUIDs from {DELETE_LIST_PATH}")

    engine = get_db_connection()

    # Optional pre-count (to know how many exist before deleting)
    pre_count_total = 0
    if DO_COUNT_BEFORE:
        with engine.connect() as conn:
            for chunk in chunked(uuids, CHUNK_SIZE):
                stmt = (
                    text(f"SELECT count(*) AS c FROM {TABLE_NAME} WHERE {PK_COLUMN} IN :ids")
                    .bindparams(bindparam("ids", expanding=True))
                )
                res = conn.execute(stmt, {"ids": chunk}).scalar_one()
                pre_count_total += int(res)
        print(f"Rows matching UUIDs (pre-check): {pre_count_total}")

    # Delete in a single transaction
    deleted_total = 0
    with engine.begin() as conn:  # transactional
        for chunk in chunked(uuids, CHUNK_SIZE):
            del_stmt = (
                text(f"DELETE FROM {TABLE_NAME} WHERE {PK_COLUMN} IN :ids")
                .bindparams(bindparam("ids", expanding=True))
            )
            result = conn.execute(del_stmt, {"ids": chunk})
            # rowcount can be -1 on some drivers; guard for that
            rc = result.rowcount if result.rowcount is not None and result.rowcount >= 0 else 0
            deleted_total += rc

    print("\nDone.")
    print(f"  UUIDs in file: {total_ids}")
    if DO_COUNT_BEFORE:
        print(f"  Rows matched before delete: {pre_count_total}")
    print(f"  Rows deleted: {deleted_total}")

if __name__ == "__main__":
    main()