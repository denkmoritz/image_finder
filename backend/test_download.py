# test_download.py
import pandas as pd
from pathlib import Path
from utils.download import download_pairs

def main():
    pkl = Path("latest_query.pkl")
    if not pkl.exists():
        print("latest_query.pkl not found. Run your /query/ first.")
        return

    df = pd.read_pickle(pkl)
    if df.empty:
        print("latest_query.pkl has no rows.")
        return

    required = ["uuid", "relation_uuid", "orig_id", "relation_orig_id"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"Missing columns: {missing}")
        return

    # just take the first 10 pairs (20 images)
    df = df.head(10)

    pairs = []
    for _, r in df.iterrows():
        if pd.notna(r["orig_id"]) and pd.notna(r["uuid"]):
            pairs.append((str(r["orig_id"]), str(r["uuid"])))
        if pd.notna(r["relation_orig_id"]) and pd.notna(r["relation_uuid"]):
            pairs.append((str(r["relation_orig_id"]), str(r["relation_uuid"])))

    print(f"Attempting to download {len(pairs)} images...")

    stats = download_pairs(pairs)

    print("\n=== Download summary ===")
    for k, v in stats.items():
        print(f"{k}: {v}")

if __name__ == "__main__":
    main()