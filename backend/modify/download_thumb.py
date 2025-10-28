#!/usr/bin/env python3
import re
import json
import time
import pathlib
from typing import Optional

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv
from tqdm import tqdm
import os

# --- Config (no CLI args) ---
CSV_PATH = "all_groups_with_orig.csv"       # columns: uuid, orig_id, group_id
OUTPUT_DIR = pathlib.Path("singapore")           # base folder for images
MANIFEST_PATH = "download_manifest.csv"     # log of attempts/results
API_BASE = "https://graph.mapillary.com"
FIELDS = "thumb_1024_url"
GROUP_FOLDER_FMT = "group_{:05d}"
# ----------------------------

def load_token() -> str:
    load_dotenv()
    token = os.getenv("MAPILLARY_TOKEN") or os.getenv("MAPILLARY_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("No Mapillary token found. Put MAPILLARY_TOKEN=... in your .env")
    return token

def clean_id(x: Optional[str]) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip()
    s = re.sub(r"\.0$", "", s)  # strip trailing .0 from CSV floats
    return s.strip().strip('"').strip("'") or None

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
    s.headers.update({"User-Agent": "mapillary-thumb-downloader/1.0"})
    return s

def fetch_thumb_url(session: requests.Session, token: str, image_id: str) -> Optional[str]:
    url = f"{API_BASE}/{image_id}"
    params = {"access_token": token, "fields": FIELDS}
    r = session.get(url, params=params, timeout=20)
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except json.JSONDecodeError:
        return None
    return data.get("thumb_1024_url")

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

def main():
    token = load_token()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Read CSV; keep orig_id as string, group_id as nullable Int64
    df = pd.read_csv(CSV_PATH, dtype={"orig_id": "string"})
    required_cols = {"orig_id", "group_id"}
    missing = required_cols - set(df.columns)
    if missing:
        raise RuntimeError(f"'{CSV_PATH}' must contain columns: {sorted(required_cols)} (missing {sorted(missing)})")

    # Clean IDs, enforce valid group_id, drop bad rows
    df["orig_id"] = df["orig_id"].map(clean_id)
    df["group_id"] = pd.to_numeric(df["group_id"], errors="coerce").astype("Int64")
    df = df.dropna(subset=["orig_id", "group_id"]).copy()

    # Deduplicate by orig_id (keep first group assignment)
    df = df.drop_duplicates(subset=["orig_id"])

    if df.empty:
        print("No valid rows (orig_id, group_id) in CSV.")
        return

    session = requests_session_with_retries()

    results = []
    for _idx, row in tqdm(df.iterrows(), total=len(df), desc="Downloading thumb_1024", unit="img"):
        image_id = row["orig_id"]
        gid = int(row["group_id"])  # guaranteed not NA now
        out_dir = OUTPUT_DIR / GROUP_FOLDER_FMT.format(gid)

        filename = f"{image_id}.jpg"
        dest = out_dir / filename

        if dest.exists():
            results.append({"orig_id": image_id, "group_id": gid, "status": "exists", "path": str(dest), "thumb_1024_url": ""})
            continue

        thumb_url = fetch_thumb_url(session, token, image_id)
        if not thumb_url:
            results.append({"orig_id": image_id, "group_id": gid, "status": "no_thumb_url", "path": "", "thumb_1024_url": ""})
            continue

        # choose extension from URL if present
        ext = pathlib.Path(thumb_url.split("?")[0]).suffix.lower()
        if ext in {".jpg", ".jpeg", ".png", ".webp"}:
            dest = dest.with_suffix(ext)

        ok = download_file(session, thumb_url, dest)
        results.append({
            "orig_id": image_id,
            "group_id": gid,
            "status": "ok" if ok else "failed",
            "path": str(dest if ok else ""),
            "thumb_1024_url": thumb_url,
        })

        time.sleep(0.01)  # polite pacing

    # Manifest
    man = pd.DataFrame(results)
    man.to_csv(MANIFEST_PATH, index=False)

    total = len(man)
    ok = (man["status"] == "ok").sum()
    exists = (man["status"] == "exists").sum()
    no_url = (man["status"] == "no_thumb_url").sum()
    failed = (man["status"] == "failed").sum()

    print(f"\nDone. Total: {total} | downloaded: {ok} | already existed: {exists} | no thumb url: {no_url} | failed: {failed}")
    print(f"Images saved under: {OUTPUT_DIR.resolve()} (per-group subfolders)")

if __name__ == "__main__":
    main()