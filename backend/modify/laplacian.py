#!/usr/bin/env python3
"""
quality_prune_by_laplacian.py

Pipeline:
  1) Read (uuid, orig_id) from berlin table
  2) Download thumb_256 for each orig_id (into ./thumb_256/)
  3) Compute Laplacian sharpness on each image
  4) Pick uuids to delete using either:
       - percentile mode: bottom PERCENTILE_DROP % (dataset-relative, default)
       - absolute mode:   score < MIN_SHARPNESS
  5) DRY-RUN prints counts and writes CSV + delete_uuids_by_quality.txt
  6) If DO_DELETE=True, delete those uuids from the DB (transactional)

Requires:
  - utils.db.get_db_connection()
  - MAPILLARY_TOKEN (or MAPILLARY_ACCESS_TOKEN) in env / .env
  - opencv-python, requests, pandas, tqdm, python-dotenv, sqlalchemy
"""

from __future__ import annotations
import os
import re
import json
import time
import math
import pathlib
from typing import Optional, List, Tuple
import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from tqdm import tqdm
import cv2
from sqlalchemy import text, bindparam
from utils.db import get_db_connection

# ------------------- Config -------------------
TABLE_NAME = "berlin"
UUID_COL = "uuid"
ORIG_ID_COL = "orig_id_x"   # Mapillary image id column

API_BASE = "https://graph.mapillary.com"
FIELDS = "thumb_256_url"

OUTPUT_DIR = pathlib.Path("thumb_256")
QUALITY_CSV = "image_quality_laplacian.csv"
DELETE_LIST_PATH = "delete_uuids_by_quality.txt"
MANIFEST_CSV = "thumb_256_manifest.csv"

# Selection mode: "percentile" (dataset-relative) or "absolute"
SELECTION_MODE = "percentile"   # "percentile" | "absolute"
PERCENTILE_DROP = 20            # drop bottom 20% sharpness (only if mode=percentile)
MIN_SHARPNESS = 60.0            # absolute cutoff (only if mode=absolute) — tune if used

# Laplacian settings
TARGET_LONG_EDGE = 256          # resize so max(h,w)=256 for consistent scoring
TRIM_BORDER = 6                 # pixels to trim on each edge to avoid black borders
LAPLACIAN_KSIZE = 3             # 3 is standard; 1 is noisy; 5+ can oversmooth
GAUSSIAN_PREBLUR = 0            # 0=off, else kernel size (odd, e.g., 3)

# Download pacing / retries
RETRY_TOTAL = 5
BACKOFF_FACTOR = 0.3
SLEEP_BETWEEN = 0.005           # seconds between thumb downloads
SKIP_EXISTING = True            # don't re-download if file already exists

# Safety
DRY_RUN = True                  # True: only compute & show counts, do NOT delete
DELETE_CHUNK = 1000             # batch size for SQL deletion
# ---------------------------------------------

def load_token() -> str:
    load_dotenv()
    token = os.getenv("MAPILLARY_TOKEN") or os.getenv("MAPILLARY_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("No Mapillary token found. Put MAPILLARY_TOKEN=... in your .env")
    return token

def requests_session_with_retries(total=5, backoff=0.5) -> requests.Session:
    retry = Retry(
        total=total,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    s = requests.Session()
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": "quality-pruner/1.0"})
    return s

def fetch_thumb256_url(session: requests.Session, token: str, image_id: str) -> Optional[str]:
    url = f"{API_BASE}/{image_id}"
    params = {"access_token": token, "fields": FIELDS}
    r = session.get(url, params=params, timeout=20)
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except json.JSONDecodeError:
        return None
    return data.get("thumb_256_url")

def clean_id(x: Optional[str]) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip()
    s = re.sub(r"\.0$", "", s)
    return s.strip().strip('"').strip("'") or None

def laplacian_sharpness_from_path(path: pathlib.Path) -> float:
    gray = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if gray is None:
        return float("nan")
    h, w = gray.shape[:2]
    # Optional resize to a standard long edge (makes scores comparable)
    if TARGET_LONG_EDGE and max(h, w) != TARGET_LONG_EDGE:
        scale = TARGET_LONG_EDGE / float(max(h, w))
        if scale != 1.0:
            nh, nw = int(round(h * scale)), int(round(w * scale))
            gray = cv2.resize(gray, (nw, nh), interpolation=cv2.INTER_AREA)
    # Optional pre-blur to reduce noise spikes
    if GAUSSIAN_PREBLUR and GAUSSIAN_PREBLUR >= 3 and GAUSSIAN_PREBLUR % 2 == 1:
        gray = cv2.GaussianBlur(gray, (GAUSSIAN_PREBLUR, GAUSSIAN_PREBLUR), 0)
    # Trim borders to avoid black frames/watermarks
    if TRIM_BORDER > 0 and min(gray.shape[:2]) > 2*TRIM_BORDER:
        gray = gray[TRIM_BORDER:-TRIM_BORDER, TRIM_BORDER:-TRIM_BORDER]
    lap = cv2.Laplacian(gray, ddepth=cv2.CV_64F, ksize=LAPLACIAN_KSIZE)
    return float(lap.var())

def download_file(session: requests.Session, url: str, dest: pathlib.Path) -> bool:
    with session.get(url, stream=True, timeout=60) as r:
        if r.status_code != 200:
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    return True

def query_all_ids() -> pd.DataFrame:
    """
    Returns DataFrame with columns: uuid, orig_id (string)
    """
    engine = get_db_connection()
    sql = f"""
        SELECT {UUID_COL} AS uuid, {ORIG_ID_COL} AS orig_id
        FROM {TABLE_NAME}
        WHERE {ORIG_ID_COL} IS NOT NULL
    """
    with engine.connect() as conn:
        df = pd.read_sql_query(sql, conn)
    df["orig_id"] = df["orig_id"].map(clean_id)
    df = df.dropna(subset=["orig_id", "uuid"]).drop_duplicates(subset=["uuid"])
    # strings
    df["uuid"] = df["uuid"].astype(str)
    df["orig_id"] = df["orig_id"].astype(str)
    return df

def decide_deletions(df_scores: pd.DataFrame) -> Tuple[pd.DataFrame, float]:
    """
    Input: df_scores with columns [uuid, orig_id, sharpness]
    Returns: (df_keep, threshold_used)
    """
    s = df_scores["sharpness"].astype(float).replace([np.inf, -np.inf], np.nan)
    valid = df_scores[s.notna()].copy()
    if valid.empty:
        return df_scores.copy(), float("nan")

    if SELECTION_MODE == "percentile":
        thr = float(np.percentile(valid["sharpness"].values, PERCENTILE_DROP))
        keep = valid["sharpness"] >= thr
    elif SELECTION_MODE == "absolute":
        thr = float(MIN_SHARPNESS)
        keep = valid["sharpness"] >= thr
    else:
        raise ValueError("SELECTION_MODE must be 'percentile' or 'absolute'")

    valid["keep"] = keep
    # merge keep flag back (NaN sharpness -> mark keep=False by default)
    out = df_scores.merge(valid[["uuid","keep"]], on="uuid", how="left")
    out["keep"] = out["keep"].fillna(False)
    return out, thr

def delete_rows(uuids: List[str]) -> int:
    engine = get_db_connection()
    deleted_total = 0
    with engine.begin() as conn:  # transactional
        for i in range(0, len(uuids), DELETE_CHUNK):
            chunk = uuids[i:i+DELETE_CHUNK]
            stmt = (
                text(f"DELETE FROM {TABLE_NAME} WHERE {UUID_COL} IN :ids")
                .bindparams(bindparam("ids", expanding=True))
            )
            res = conn.execute(stmt, {"ids": chunk})
            rc = res.rowcount if res.rowcount is not None and res.rowcount >= 0 else 0
            deleted_total += rc
    return deleted_total

def main():
    token = load_token()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1) Query IDs
    df_ids = query_all_ids()
    total_rows = len(df_ids)
    if total_rows == 0:
        print("No rows with orig_id found.")
        return
    print(f"Found {total_rows} rows in {TABLE_NAME}.")

    session = requests_session_with_retries(RETRY_TOTAL, BACKOFF_FACTOR)

    # 2) Download and score
    records = []
    manifest = []
    for uuid, orig_id in tqdm(df_ids[["uuid","orig_id"]].itertuples(index=False), total=total_rows, desc="thumb_256 + Laplacian"):
        # set destination path
        dest = OUTPUT_DIR / f"{orig_id}.jpg"

        # maybe skip if already exists
        if SKIP_EXISTING and dest.exists():
            status = "exists"
        else:
            url = fetch_thumb256_url(session, token, orig_id)
            if not url:
                manifest.append({"uuid": uuid, "orig_id": orig_id, "status": "no_thumb_url", "path": "", "thumb_256_url": ""})
                continue
            # choose extension by URL
            ext = pathlib.Path(url.split("?")[0]).suffix.lower()
            if ext in {".jpg", ".jpeg", ".png", ".webp"}:
                dest = dest.with_suffix(ext)
            ok = download_file(session, url, dest)
            status = "ok" if ok else "failed"
            time.sleep(SLEEP_BETWEEN)

        manifest.append({"uuid": uuid, "orig_id": orig_id, "status": status, "path": str(dest if dest.exists() else ""), "thumb_256_url": ""})

        # 3) score (only if file present)
        if dest.exists():
            score = laplacian_sharpness_from_path(dest)
        else:
            score = float("nan")

        records.append({"uuid": uuid, "orig_id": orig_id, "path": str(dest), "sharpness": score})

    # Write manifest & quality CSV
    pd.DataFrame(manifest).to_csv(MANIFEST_CSV, index=False)
    df_scores = pd.DataFrame(records)
    df_scores.to_csv(QUALITY_CSV, index=False)

    # 4) Decide deletions
    df_decided, threshold_used = decide_deletions(df_scores)
    to_delete_df = df_decided.loc[~df_decided["keep"], ["uuid","orig_id","sharpness","path"]].copy()
    keep_df = df_decided.loc[df_decided["keep"], ["uuid"]]

    # Report
    n_valid = df_scores["sharpness"].notna().sum()
    n_keep = len(keep_df)
    n_del = len(to_delete_df)
    print("\n--- Laplacian quality pruning ---")
    print(f"Mode: {SELECTION_MODE} | Threshold: {threshold_used:.4f}" if not math.isnan(threshold_used) else f"Mode: {SELECTION_MODE}")
    print(f"Images scored: {n_valid}/{total_rows}")
    print(f"Would KEEP:    {n_keep}")
    print(f"Would DELETE:  {n_del}")

    # Write delete list (uuids)
    with open(DELETE_LIST_PATH, "w", encoding="utf-8") as f:
        for u in to_delete_df["uuid"].astype(str):
            f.write(u + "\n")
    print(f"UUID delete list written to: {DELETE_LIST_PATH}")
    print(f"Per-image quality CSV written to: {QUALITY_CSV}")
    print(f"Download manifest written to: {MANIFEST_CSV}")

    # 5) Optional DB deletion
    if not DRY_RUN and n_del > 0:
        print("\nDeleting from DB ...")
        deleted = delete_rows(to_delete_df["uuid"].astype(str).tolist())
        print(f"Deleted rows: {deleted}")
    elif DRY_RUN:
        print("\nDRY_RUN is True — no rows deleted. Flip DRY_RUN=False to apply.")

if __name__ == "__main__":
    main()