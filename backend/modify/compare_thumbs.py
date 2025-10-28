#!/usr/bin/env python3
from __future__ import annotations, absolute_import, division, print_function

import os
import re
import sys
import itertools
from collections import defaultdict, deque
from typing import Callable, Dict, List, Tuple, Iterable, Set, Optional

from PIL import Image, UnidentifiedImageError
import imagehash

try:
    from tqdm import tqdm
    TQDM = True
except Exception:
    TQDM = False

# --------- Config (no CLI args) ---------
IMAGES_DIR = "singapore"                 # base folder with per-group subfolders, e.g., <city>/group_00012/*.jpg
RECURSIVE = True                    # scan subfolders
HASH_METHOD = "phash"               # ahash|phash|dhash|whash-haar|whash-db4|colorhash|crop-resistant
HASH_SIZE = 16                      # 8 or 16 typical
SIMILAR_THRESHOLD = 10              # Hamming distance <= this = near-duplicate
UUID_MAP_CSV = "all_groups_with_orig.csv"  # must contain columns: uuid, orig_id, group_id
OUTPUT_DELETE_UUIDS = "delete_uuids.txt"   # <-- only output we write
# ----------------------------------------

# Keeper policy (set True/False to taste)
KEEP_POLICY = {
    "keep_one_per_exact_group": True,   # keep 1 file for each exact-duplicate hash group
    "keep_one_per_sim_cluster": True,   # keep 1 file for each similarity cluster
    "keep_all_singletons": True,        # keep all images that have no similar neighbors
}

IMG_EXTS = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff")

def is_image(filename: str) -> bool:
    return filename.lower().endswith(IMG_EXTS)

def iter_files(root: str, recursive: bool = False) -> Iterable[str]:
    if recursive:
        for dirpath, _dirs, files in os.walk(root):
            for fn in files:
                if is_image(fn):
                    yield os.path.join(dirpath, fn)
    else:
        for fn in os.listdir(root):
            if is_image(fn):
                yield os.path.join(root, fn)

def get_hashfunc(method: str, hash_size: int) -> Callable[[Image.Image], imagehash.ImageHash]:
    m = method.lower()
    if m == "ahash":
        return lambda img: imagehash.average_hash(img, hash_size=hash_size)
    if m == "phash":
        return lambda img: imagehash.phash(img, hash_size=hash_size)
    if m == "dhash":
        return lambda img: imagehash.dhash(img, hash_size=hash_size)
    if m == "whash-haar":
        return lambda img: imagehash.whash(img, hash_size=hash_size)
    if m == "whash-db4":
        return lambda img: imagehash.whash(img, hash_size=hash_size, mode="db4")
    if m == "colorhash":
        return lambda img: imagehash.colorhash(img)  # ignores hash_size
    if m == "crop-resistant":
        return lambda img: imagehash.crop_resistant_hash(img)
    raise ValueError(f"Unknown hash method: {method}")

def compute_hashes(paths: List[str], hashfunc: Callable[[Image.Image], imagehash.ImageHash]) -> Dict[str, imagehash.ImageHash]:
    results = {}
    it = tqdm(paths, desc="Hashing", unit="img") if TQDM else paths
    for p in it:
        try:
            with Image.open(p) as im:
                im.load()
                results[p] = hashfunc(im)
        except (UnidentifiedImageError, OSError) as e:
            print(f"Skipping unreadable image: {p} ({e})", file=sys.stderr)
        except Exception as e:
            print(f"Problem hashing {p}: {e}", file=sys.stderr)
    return results

def group_exact_duplicates(hashes: Dict[str, imagehash.ImageHash]) -> Dict[str, List[str]]:
    groups = defaultdict(list)
    for path, h in hashes.items():
        groups[str(h)].append(path)
    return {k: v for k, v in groups.items() if len(v) > 1}

def find_similar_pairs(hashes: Dict[str, imagehash.ImageHash], threshold: int) -> List[Tuple[str, str, int]]:
    # light bucketing for speed
    buckets = defaultdict(list)
    for path, h in hashes.items():
        buckets[str(h)[:3]].append((path, h))
    pairs = []
    outer = tqdm(buckets.items(), desc="Comparing", unit="bucket") if TQDM else buckets.items()
    for _prefix, items in outer:
        for (p1, h1), (p2, h2) in itertools.combinations(items, 2):
            d = h1 - h2
            if d <= threshold and p1 != p2:
                a, b = sorted([p1, p2])
                pairs.append((a, b, d))
    return sorted(set(pairs), key=lambda x: (x[2], x[0], x[1]))

def build_graph(pairs: List[Tuple[str, str, int]]) -> Dict[str, Dict[str, int]]:
    g: Dict[str, Dict[str, int]] = defaultdict(dict)
    for a, b, d in pairs:
        g[a][b] = d
        g[b][a] = d
    return g

def connected_components(graph: Dict[str, Dict[str, int]]) -> List[Set[str]]:
    seen: Set[str] = set()
    comps: List[Set[str]] = []
    for node in graph:
        if node in seen:
            continue
        q = deque([node])
        seen.add(node)
        comp = set()
        while q:
            u = q.popleft()
            comp.add(u)
            for v in graph[u]:
                if v not in seen:
                    seen.add(v)
                    q.append(v)
        comps.append(comp)
    return comps

def file_stats(path: str) -> Tuple[int, float]:
    try:
        st = os.stat(path)
        return (int(st.st_size), float(st.st_mtime))
    except Exception:
        return (0, 0.0)

def choose_representative_among(paths: List[str],
                                graph: Dict[str, Dict[str, int]]) -> str:
    """
    Pick a 'best' representative among a set:
    1) higher degree, 2) lower edge-sum, 3) larger file, 4) newer mtime, 5) lexicographic path
    """
    scored = []
    for p in paths:
        neighbors = graph.get(p, {})
        degree = len(neighbors)
        edge_sum = sum(neighbors.values()) if neighbors else 0
        size, mtime = file_stats(p)
        scored.append((-degree, edge_sum, -size, -mtime, p))
    scored.sort()
    return scored[0][4] if scored else sorted(paths)[0]

def load_uuid_map(csv_path: str) -> Dict[str, str]:
    """
    Load all_groups_with_orig.csv and return orig_id -> uuid mapping.
    We assume filenames are <orig_id>.<ext>.
    """
    import pandas as pd
    df = pd.read_csv(csv_path, dtype={"orig_id": "string", "uuid": "string"})
    if "orig_id" not in df.columns or "uuid" not in df.columns:
        raise RuntimeError(f"{csv_path} must contain 'orig_id' and 'uuid' columns.")
    # drop duplicates, prefer first occurrence
    df = df.dropna(subset=["orig_id", "uuid"]).drop_duplicates(subset=["orig_id"])
    return dict(zip(df["orig_id"].astype(str), df["uuid"].astype(str)))

def path_to_orig_id(p: str) -> Optional[str]:
    base = os.path.basename(p)
    # strip extension; allow dots before extension just in case
    if "." not in base:
        return None
    return ".".join(base.split(".")[:-1])

def main():
    if not os.path.isdir(IMAGES_DIR):
        print(f"Directory not found: {IMAGES_DIR}")
        sys.exit(1)

    # Collect files
    paths = sorted(iter_files(IMAGES_DIR, recursive=RECURSIVE))
    if not paths:
        print(f"No images found in {IMAGES_DIR}")
        # still create an empty delete file
        open(OUTPUT_DELETE_UUIDS, "w", encoding="utf-8").close()
        sys.exit(0)

    # Hash & compare
    hashfunc = get_hashfunc(HASH_METHOD, HASH_SIZE)
    hashes = compute_hashes(paths, hashfunc)
    dup_groups = group_exact_duplicates(hashes)
    similar_pairs = find_similar_pairs(hashes, SIMILAR_THRESHOLD)

    # Build similarity graph & components
    graph = build_graph(similar_pairs)
    components = connected_components(graph) if graph else []
    components_sorted = sorted(components, key=lambda s: (-len(s), sorted(s)[0] if s else ""))

    # Map: exact hash -> files; and path -> (exact_hash, exact_gid)
    exact_hash_to_gid: Dict[str, int] = {}
    for i, (h, files) in enumerate(sorted(dup_groups.items(), key=lambda kv: (-len(kv[1]), kv[0])), start=1):
        exact_hash_to_gid[h] = i
    path_to_exact: Dict[str, Tuple[Optional[str], Optional[int]]] = {}
    for h, files in dup_groups.items():
        gid = exact_hash_to_gid[h]
        for p in files:
            path_to_exact[p] = (h, gid)
    for p in paths:
        if p not in path_to_exact:
            path_to_exact[p] = (None, None)

    # Decide representatives to KEEP
    keep: Set[str] = set()

    # 1) Singletons (no edges)
    if KEEP_POLICY["keep_all_singletons"]:
        for p in paths:
            if p not in graph:  # no neighbors
                keep.add(p)

    # 2) One per exact duplicate group
    if KEEP_POLICY["keep_one_per_exact_group"]:
        for h, files in dup_groups.items():
            rep = choose_representative_among(files, graph)
            keep.add(rep)

    # 3) One per similarity cluster
    if KEEP_POLICY["keep_one_per_sim_cluster"]:
        for comp in components_sorted:
            rep = choose_representative_among(sorted(list(comp)), graph)
            keep.add(rep)

    # Everything else is to delete
    to_delete_paths = [p for p in paths if p not in keep]

    # Convert paths -> orig_id -> uuid
    orig_to_uuid = load_uuid_map(UUID_MAP_CSV)
    delete_uuids: List[str] = []
    missing_map = 0
    for p in to_delete_paths:
        oid = path_to_orig_id(p)
        if not oid:
            missing_map += 1
            continue
        uuid = orig_to_uuid.get(oid)
        if uuid:
            delete_uuids.append(uuid)
        else:
            missing_map += 1

    # De-duplicate UUIDs, keep stable order
    seen = set()
    deduped = []
    for u in delete_uuids:
        if u not in seen:
            seen.add(u)
            deduped.append(u)

    # Write the ONLY output
    with open(OUTPUT_DELETE_UUIDS, "w", encoding="utf-8") as f:
        for u in deduped:
            f.write(u + "\n")

    total = len(paths)
    kept = len(keep)
    print(
        f"\nDone.\n"
        f"  Scanned images: {total}\n"
        f"  Representatives kept: {kept}\n"
        f"  UUIDs to delete: {len(deduped)}  (written to {OUTPUT_DELETE_UUIDS})\n"
        + (f"  Note: {missing_map} files had no uuid mapping in {UUID_MAP_CSV}\n" if missing_map else "")
    )

if __name__ == "__main__":
    main()