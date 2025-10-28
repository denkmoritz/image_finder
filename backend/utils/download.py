import os
from pathlib import Path
from typing import Iterable, Tuple, Dict, List
import requests
from dotenv import load_dotenv
from config import IMAGES_DIR

GRAPH_BASE = "https://graph.mapillary.com"
URL_FIELD = "thumb_original_url"

load_dotenv()
TOKEN = os.getenv("MAPILLARY_TOKEN")
if not TOKEN:
    raise RuntimeError("MAPILLARY_TOKEN not set. Put MAPILLARY_TOKEN=MLY|... in your env or .env")

def _local_path(dest_name: str, city: str) -> Path:
    """Save as images/{city}/{uuid}.jpg"""
    city_dir = IMAGES_DIR / city
    city_dir.mkdir(parents=True, exist_ok=True)
    return city_dir / f"{dest_name}.jpg"

def _fetch_url_single(image_id: str) -> str | None:
    """Fetch thumb_original_url for a single image id (no batching)."""
    url = f"{GRAPH_BASE}/{image_id}?fields=id,{URL_FIELD}&access_token={TOKEN}"
    r = requests.get(url, timeout=12)
    if r.status_code != 200:
        print(f"[META-HTTP-{r.status_code}] id={image_id} body={r.text[:200]}", flush=True)
        return None
    j = r.json()
    u = j.get(URL_FIELD)
    if not u:
        print(f"[META-MISS] id={image_id} has no {URL_FIELD}", flush=True)
        return None
    return u

def download_pairs(pairs: Iterable[Tuple[str, str]], city: str) -> Dict:
    """
    pairs: (fetch_id -> Mapillary image id, dest_name -> UUID)
    city: City name (e.g., "berlin", "paris", "washington", "singapore")
    Downloads original (thumb_original_url) and saves as images/{city}/{uuid}.jpg
    Prints: 'Image <fetch_id> downloaded and saved under <path>'
    """
    city = city.lower()
    
    # Create city-specific directory
    city_dir = IMAGES_DIR / city
    city_dir.mkdir(parents=True, exist_ok=True)
    
    # de-dupe + clean
    seen = set()
    uniq_pairs: List[Tuple[str, str]] = []
    for fid, dest in pairs:
        fid, dest = str(fid).strip(), str(dest).strip()
        if fid and dest and (fid, dest) not in seen:
            seen.add((fid, dest))
            uniq_pairs.append((fid, dest))
    
    # skip existing
    to_fetch = []
    skipped_existing = 0
    for fid, dest in uniq_pairs:
        path = _local_path(dest, city)
        if path.exists() and path.stat().st_size > 0:
            skipped_existing += 1
        else:
            to_fetch.append((fid, dest))
    
    downloaded = 0
    missing_meta, failed = [], []
    
    for fid, dest in to_fetch:
        # 1) per-id metadata call (works like your curl)
        url = _fetch_url_single(fid)
        if not url:
            missing_meta.append(fid)
            continue
        
        # 2) download
        try:
            resp = requests.get(url, timeout=20)
            if resp.status_code == 200 and resp.content:
                path = _local_path(dest, city)
                path.write_bytes(resp.content)
                downloaded += 1
                print(f"Image {fid} downloaded and saved under {path}", flush=True)
            else:
                failed.append((fid, dest))
                print(f"[FAIL] download HTTP {resp.status_code} for id={fid}", flush=True)
        except requests.RequestException as e:
            failed.append((fid, dest))
            print(f"[FAIL] exception for id={fid}: {e}", flush=True)
    
    return {
        "city": city,
        "requested_pairs": len(uniq_pairs),
        "skipped_existing": skipped_existing,
        "attempted": len(to_fetch),
        "downloaded": downloaded,
        "missing_meta": missing_meta[:5],
        "failed": failed[:5],
        "images_dir": str(city_dir.resolve()),
    }