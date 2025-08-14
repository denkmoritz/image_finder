#!/usr/bin/env python3
import os
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

# --- Config (no CLI args) ---
CSV_PATH = "largest_group_with_orig.csv"   # input with columns: uuid, orig_id
OUTPUT_DIR = pathlib.Path("thumb_256")     # where images will be saved
MANIFEST_PATH = "download_manifest.csv"    # log of attempts/results
API_BASE = "https://graph.mapillary.com"
FIELDS = "thumb_256_url"                   # minimal field set we need
# ----------------------------

def load_token() -> str:
    load_dotenv()  # reads .env from current directory by default
    token = os.getenv("MAPILLARY_TOKEN") or os.getenv("MAPILLARY_ACCESS_TOKEN")
    if not token:
        raise RuntimeError("No Mapillary token found. Put MAPILLARY_TOKEN=... in your .env")
    return token

def clean_id(x: Optional[str]) -> Optional[str]:
    if x is None:
        return None
    s = str(x).strip()
    # strip a trailing ".0" (common when IDs came from a floaty CSV)
    s = re.sub(r"\.0$", "", s)
    # remove accidental spaces/quotes
    s = s.strip().strip('"').strip("'")
    return s or None

def requests_session_with_retries(total=5, backoff=0.5) -> requests.Session:
    retry = Retry(
        total=total,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s = requests.Session()
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({"User-Agent": "mapillary-thumb-downloader/1.0"})
    return s

def fetch_thumb_url(session: requests.Session, token: str, image_id: str) -> Optional[str]:
    """Query Graph API for a single image's thumb_256_url."""
    url = f"{API_BASE}/{image_id}"
    params = {
        "access_token": token,
        "fields": FIELDS,
    }
    r = session.get(url, params=params, timeout=20)
    if r.status_code != 200:
        return None
    try:
        data = r.json()
    except json.JSONDecodeError:
        return None
    return data.get("thumb_256_url")

def download_file(session: requests.Session, url: str, dest: pathlib.Path) -> bool:
    """Stream download to file; returns True if saved."""
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

    # Read CSV as strings to preserve IDs exactly
    df = pd.read_csv(CSV_PATH, dtype={"orig_id": "string"})
    if "orig_id" not in df.columns:
        raise RuntimeError(f"'{CSV_PATH}' must contain an 'orig_id' column.")

    # Clean & de-duplicate IDs
    df["orig_id"] = df["orig_id"].map(clean_id)
    ids = (
        df["orig_id"]
        .dropna()
        .drop_duplicates()
        .tolist()
    )
    if not ids:
        print("No valid orig_id values found in the CSV.")
        return

    session = requests_session_with_retries()

    results = []  # for manifest
    for image_id in tqdm(ids, desc="Downloading thumb_256", unit="img"):
        # file path: thumb_256/<id>.jpg (or .png if we detect extension)
        # We'll default to .jpg unless response suggests otherwise.
        filename = f"{image_id}.jpg"
        dest = OUTPUT_DIR / filename

        # Skip if already exists
        if dest.exists():
            results.append({"orig_id": image_id, "status": "exists", "path": str(dest), "thumb_256_url": ""})
            continue

        thumb_url = fetch_thumb_url(session, token, image_id)
        if not thumb_url:
            results.append({"orig_id": image_id, "status": "no_thumb_url", "path": "", "thumb_256_url": ""})
            continue

        # Try to pick extension from URL if present
        ext = pathlib.Path(thumb_url.split("?")[0]).suffix.lower()
        if ext in {".jpg", ".jpeg", ".png", ".webp"}:
            dest = dest.with_suffix(ext)

        ok = download_file(session, thumb_url, dest)
        results.append({
            "orig_id": image_id,
            "status": "ok" if ok else "failed",
            "path": str(dest if ok else ""),
            "thumb_256_url": thumb_url,
        })

        # Light pacing to be nice to the API/CDN; adjust if needed
        time.sleep(0.01)

    # Write a manifest so you know what happened
    pd.DataFrame(results).to_csv(MANIFEST_PATH, index=False)
    total = len(results)
    ok = sum(1 for r in results if r["status"] == "ok")
    skipped = sum(1 for r in results if r["status"] == "exists")
    missing = sum(1 for r in results if r["status"] == "no_thumb_url")
    failed = sum(1 for r in results if r["status"] == "failed")

    print(f"\nDone. Total: {total} | downloaded: {ok} | already existed: {skipped} | no thumb url: {missing} | failed: {failed}")
    print(f"Images saved to: {OUTPUT_DIR.resolve()}")
    print(f"Manifest: {pathlib.Path(MANIFEST_PATH).resolve()}")

if __name__ == "__main__":
    main()