# utils/download.py
from __future__ import annotations
import os, asyncio
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Literal

import aiohttp
from dotenv import load_dotenv
from config import THUMB_DIR

GRAPH_BASE = "https://graph.mapillary.com"
BATCH_SIZE = 50
API_TIMEOUT_S = 10.0
DL_TIMEOUT_S = 20.0
RETRIES = 3
CONCURRENCY = 16

# ---------- env/token ----------
load_dotenv()
TOKEN = os.getenv("MAPILLARY_TOKEN")
if not TOKEN:
    raise RuntimeError("MAPILLARY_TOKEN not found. Create a .env with MAPILLARY_TOKEN=MLY|...")

# ---------- helpers ----------
Variant = Literal["thumb_256", "original"]

def _variant_subdir(variant: Variant) -> Path:
    return THUMB_DIR / ("thumb_256" if variant == "thumb_256" else "original")

def _local_path(uid: str, variant: Variant) -> Path:
    # we normalize to .jpg for simplicity
    return _variant_subdir(variant) / f"{uid}.jpg"

def _safe_ext_from_content_type(ct: Optional[str]) -> str:
    if not ct:
        return ".jpg"
    ct = ct.lower().split(";")[0].strip()
    return {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(ct, ".jpg")

async def _get_json(session: aiohttp.ClientSession, url: str, *, timeout: float) -> Optional[dict]:
    attempt = 0
    while attempt <= RETRIES:
        attempt += 1
        try:
            async with session.get(url, timeout=timeout) as resp:
                if resp.status == 200:
                    return await resp.json()
                if resp.status == 429:
                    retry_after = float(resp.headers.get("Retry-After", "1"))
                    await asyncio.sleep(retry_after)
                elif 500 <= resp.status < 600:
                    pass
                else:
                    return None
        except (aiohttp.ClientError, asyncio.TimeoutError):
            pass
        await asyncio.sleep(min(2 ** (attempt - 1), 10))
    return None

async def _download_file(session: aiohttp.ClientSession, url: str, dest: Path, *, timeout: float) -> bool:
    attempt = 0
    tmp = dest.with_suffix(dest.suffix + ".part")
    while attempt <= RETRIES:
        attempt += 1
        try:
            async with session.get(url, timeout=timeout) as resp:
                if resp.status == 200:
                    if dest.suffix == "":
                        ext = _safe_ext_from_content_type(resp.headers.get("Content-Type"))
                        dest = dest.with_suffix(ext)
                        tmp = dest.with_suffix(dest.suffix + ".part")
                    data = await resp.read()
                    if not data:
                        return False
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    tmp.write_bytes(data)
                    tmp.replace(dest)
                    return True
                if resp.status == 429:
                    retry_after = float(resp.headers.get("Retry-After", "1"))
                    await asyncio.sleep(retry_after)
                elif 500 <= resp.status < 600:
                    pass
                else:
                    return False
        except (aiohttp.ClientError, asyncio.TimeoutError):
            pass
        await asyncio.sleep(min(2 ** (attempt - 1), 10))
    return False

# ---------- Mapillary metadata ----------
def _field_for_variant(variant: Variant) -> str:
    # Mapillary fields list includes:
    #  - thumb_256_url
    #  - thumb_original_url  (use this as “original image” URL)
    return "thumb_256_url" if variant == "thumb_256" else "thumb_original_url"

async def _fetch_meta_batch(session: aiohttp.ClientSession, ids: List[str], *, variant: Variant) -> Dict[str, str]:
    """
    GET /images?ids=...&fields=id,<chosen_field>
    Returns {id: url}
    """
    if not ids:
        return {}
    field = _field_for_variant(variant)
    ids_csv = ",".join(ids)
    url = (
        f"{GRAPH_BASE}/images?access_token={TOKEN}"
        f"&ids={ids_csv}&fields=id,{field}"
    )
    j = await _get_json(session, url, timeout=API_TIMEOUT_S)
    if not j:
        return {}
    out: Dict[str, str] = {}
    data = j.get("data")
    if isinstance(data, list):
        for item in data:
            iid = item.get("id")
            turl = item.get(field)
            if iid and turl:
                out[iid] = turl
    else:
        # single-object fallback
        iid = j.get("id")
        turl = j.get(field)
        if iid and turl:
            out[iid] = turl
    return out

# ---------- public API ----------
async def download_all(ids: Iterable[str], *, variant: Variant = "thumb_256", concurrency: int = CONCURRENCY) -> Set[str]:
    """
    Download either 'thumb_256' or 'original' (thumb_original_url) for given IDs.
    Returns IDs that now exist locally.
    """
    ids = list(dict.fromkeys(str(i) for i in ids))  # dedupe, keep order
    out_dir = _variant_subdir(variant)
    out_dir.mkdir(parents=True, exist_ok=True)

    ok_ids: Set[str] = set()
    to_fetch: List[str] = []
    for uid in ids:
        p = _local_path(uid, variant)
        if p.exists() and p.stat().st_size > 0:
            ok_ids.add(uid)
        else:
            to_fetch.append(uid)

    if not to_fetch:
        return ok_ids

    sem = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession() as session:
        # 1) batch metadata
        meta: Dict[str, str] = {}
        for i in range(0, len(to_fetch), BATCH_SIZE):
            chunk = to_fetch[i:i + BATCH_SIZE]
            meta.update(await _fetch_meta_batch(session, chunk, variant=variant))

        # 2) download concurrently
        async def dl_one(uid: str):
            url = meta.get(uid)
            if not url:
                return
            dest = _local_path(uid, variant)  # normalized .jpg
            async with sem:
                ok = await _download_file(session, url, dest, timeout=DL_TIMEOUT_S)
            if ok:
                ok_ids.add(uid)

        await asyncio.gather(*(dl_one(uid) for uid in to_fetch))

    return ok_ids

def build_thumb_paths(ok_ids: Iterable[str], *, variant: Variant = "thumb_256") -> Dict[str, str]:
    """
    Build {uuid: local_path} for the chosen variant.
    """
    out: Dict[str, str] = {}
    for uid in ok_ids:
        p = _local_path(uid, variant)
        if p.exists() and p.stat().st_size > 0:
            out[uid] = str(p)
    return out

from typing import Iterable, Set, Dict

# Always thumb_256
async def download_thumbs_256(ids: Iterable[str]) -> Set[str]:
    return await download_all(ids, variant="thumb_256")

def build_thumb256_paths(ok_ids: Iterable[str]) -> Dict[str, str]:
    return build_thumb_paths(ok_ids, variant="thumb_256")

# For the separate download API (originals)
async def download_originals(ids: Iterable[str]) -> Set[str]:
    return await download_all(ids, variant="original")

def build_original_paths(ok_ids: Iterable[str]) -> Dict[str, str]:
    return build_thumb_paths(ok_ids, variant="original")