#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import json
import requests
from dotenv import load_dotenv

# Load .env (optional: API_BASE)
load_dotenv()
API_BASE = os.getenv("API_BASE", "http://localhost:8000").rstrip("/")
URL = f"{API_BASE}/query/"

# Fixed payload per your request
payload = {
    "inner_buffer": 8.0,
    "outer_buffer": 9.0
}

def main():
    try:
        resp = requests.post(URL, json=payload, timeout=120)
    except requests.RequestException as e:
        print(f"Request failed: {e}", file=sys.stderr)
        sys.exit(1)

    if resp.status_code != 200:
        print(f"HTTP {resp.status_code}: {resp.text}", file=sys.stderr)
        sys.exit(1)

    try:
        data = resp.json()
    except json.JSONDecodeError:
        print("Server returned non-JSON response.", file=sys.stderr)
        print(resp.text)
        sys.exit(1)

    # Pretty summary
    print("=== /query result (8m / 9m) ===")
    print(f"count_pairs:           {data.get('count_pairs')}")
    print(f"count_geo_groups:      {data.get('count_geo_groups')}")
    print(f"count_unique_ids:      {data.get('count_unique_ids')}")
    print(f"count_thumbs_available:{data.get('count_thumbs_available')}")
    print(f"count_final_ids:       {data.get('count_final_ids')}")
    # Optional: show first few final IDs
    final_ids = data.get("final_ids") or []
    print(f"final_ids (first 10):  {final_ids[:10]}")

    # Full JSON (pretty)
    print("\n--- Raw JSON ---")
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    main()