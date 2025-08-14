#!/usr/bin/env python3
from __future__ import absolute_import, division, print_function

import os
import sys
import itertools
from collections import defaultdict
from typing import Callable, Dict, List, Tuple, Iterable

from PIL import Image, UnidentifiedImageError
import imagehash

try:
    from tqdm import tqdm
    TQDM = True
except Exception:
    TQDM = False

# --------- Config (no CLI args) ---------
IMAGES_DIR = "thumb_256"      # folder that contains your downloaded thumbs
RECURSIVE = False             # set True to scan subfolders
HASH_METHOD = "phash"         # one of: ahash|phash|dhash|whash-haar|whash-db4|colorhash|crop-resistant
HASH_SIZE = 16                # larger = slower but more discriminative (typical: 8 or 16)
SIMILAR_THRESHOLD = 5         # Hamming distance <= this is considered "near-duplicate"
OUTPUT_EXACT = "thumb_dupes_exact.csv"
OUTPUT_SIMILAR = "thumb_dupes_similar.csv"
OUTPUT_SUMMARY = "thumb_dupes_summary.txt"
# ---------------------------------------

# map method string -> callable factory
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
        return lambda img: imagehash.colorhash(img)  # colorhash ignores hash_size
    if m == "crop-resistant":
        return lambda img: imagehash.crop_resistant_hash(img)
    raise ValueError(f"Unknown hash method: {method}")

def is_image(filename: str) -> bool:
    f = filename.lower()
    return f.endswith((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp", ".tiff"))

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

def compute_hashes(paths: List[str], hashfunc: Callable[[Image.Image], imagehash.ImageHash]) -> Dict[str, imagehash.ImageHash]:
    results = {}
    it = tqdm(paths, desc="Hashing", unit="img") if TQDM else paths
    for p in it:
        try:
            with Image.open(p) as im:
                # Ensure a consistent mode/size handling for robust hashing
                im.load()
                results[p] = hashfunc(im)
        except (UnidentifiedImageError, OSError) as e:
            print(f"Skipping unreadable image: {p} ({e})", file=sys.stderr)
        except Exception as e:
            print(f"Problem hashing {p}: {e}", file=sys.stderr)
    return results

def write_csv(path: str, rows: List[Tuple]):
    import csv
    if not rows:
        # still create an empty file with header if we can infer it
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # Try to write a generic header
            writer.writerow(["img_a","img_b","distance","relation","hash_method","hash_size"])
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # header
        if len(rows[0]) == 6:
            writer.writerow(["img_a","img_b","distance","relation","hash_method","hash_size"])
        elif len(rows[0]) == 4:
            writer.writerow(["hash_hex","count","hash_method","hash_size"])
        writer.writerows(rows)

def group_exact_duplicates(hashes: Dict[str, imagehash.ImageHash]) -> Dict[str, List[str]]:
    groups = defaultdict(list)
    for path, h in hashes.items():
        groups[str(h)].append(path)  # str(h) is the hex string of the hash
    # keep only groups with >1 image
    return {k: v for k, v in groups.items() if len(v) > 1}

def find_similar_pairs(hashes: Dict[str, imagehash.ImageHash], threshold: int) -> List[Tuple[str, str, int]]:
    # Light bucketing: group by the first few hex chars to avoid O(n^2) on big sets.
    # With HASH_SIZE=16, hash length is 16*16/4 = 64 bits -> 16 hex chars. Use first 3 as a coarse bucket.
    buckets = defaultdict(list)
    for path, h in hashes.items():
        hexs = str(h)
        buckets[hexs[:3]].append((path, h))
    pairs = []
    outer = tqdm(buckets.items(), desc="Comparing", unit="bucket") if TQDM else buckets.items()
    for _prefix, items in outer:
        for (p1, h1), (p2, h2) in itertools.combinations(items, 2):
            d = h1 - h2  # Hamming distance
            if d <= threshold and p1 != p2:
                a, b = sorted([p1, p2])
                pairs.append((a, b, d))
    # Deduplicate pairs if any repeated via different buckets (shouldn't, but be safe)
    pairs = sorted(set(pairs), key=lambda x: (x[2], x[0], x[1]))
    return pairs

def main():
    if not os.path.isdir(IMAGES_DIR):
        print(f"Directory not found: {IMAGES_DIR}")
        sys.exit(1)

    paths = sorted(iter_files(IMAGES_DIR, recursive=RECURSIVE))
    if not paths:
        print(f"No images found in {IMAGES_DIR}")
        sys.exit(0)

    hashfunc = get_hashfunc(HASH_METHOD, HASH_SIZE)
    hashes = compute_hashes(paths, hashfunc)

    # Exact duplicates (distance 0 => identical hash)
    dup_groups = group_exact_duplicates(hashes)
    exact_rows = []
    for hex_hash, files in dup_groups.items():
        exact_rows.append((hex_hash, len(files), HASH_METHOD, HASH_SIZE))
    write_csv(OUTPUT_EXACT, exact_rows)

    # Near duplicates within threshold
    similar_pairs = find_similar_pairs(hashes, SIMILAR_THRESHOLD)
    similar_rows = [
        (a, b, dist, "exact" if dist == 0 else "similar", HASH_METHOD, HASH_SIZE)
        for (a, b, dist) in similar_pairs
    ]
    write_csv(OUTPUT_SIMILAR, similar_rows)

    # Write a human-readable summary
    total = len(paths)
    exact_groups = len(dup_groups)
    exact_images = sum(len(v) for v in dup_groups.values())
    similar_edges = len(similar_pairs)

    with open(OUTPUT_SUMMARY, "w", encoding="utf-8") as f:
        f.write(f"Hash method: {HASH_METHOD}, size={HASH_SIZE}\n")
        f.write(f"Scanned images: {total}\n")
        f.write(f"Exact duplicate groups: {exact_groups} (images in dup groups: {exact_images})\n")
        f.write(f"Similar pairs (distance <= {SIMILAR_THRESHOLD}): {similar_edges}\n\n")
        if dup_groups:
            f.write("Example exact-duplicate groups:\n")
            for i, (h, files) in enumerate(list(dup_groups.items())[:10], start=1):
                f.write(f"  {i:02d}  hash={h}  count={len(files)}\n")
                for fp in files[:5]:
                    f.write(f"       - {fp}\n")
                if len(files) > 5:
                    f.write("       - ...\n")

    print(f"\nDone.\n"
          f"  Scanned: {total} images\n"
          f"  Exact duplicate groups: {exact_groups} (see {OUTPUT_EXACT})\n"
          f"  Similar pairs (≤ {SIMILAR_THRESHOLD}): {similar_edges} (see {OUTPUT_SIMILAR})\n"
          f"  Summary: {OUTPUT_SUMMARY}")

if __name__ == "__main__":
    main()