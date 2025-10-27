import pandas as pd
from pathlib import Path
from datetime import datetime
import re
import sqlite3

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from utils.plot_slice import plot_slice
from utils.query import run_query
from utils.create_slice import create_materialized_view
from utils.download import download_pairs
from utils.helper_db import *
from utils.pydantic_models import *

from config import IMAGES_DIR

PKL_PATH = Path("latest_query.pkl")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins = ["*"],
    allow_methods = ["*"],
    allow_headers = ["*"],
    allow_credentials = True
)

@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/plot-slice/")
async def plot(data: PlotRequest):
    if data.inner_buffer >= data.outer_buffer:
        raise HTTPException(status_code=400, detail="Outer Ring must be greater than Inner Ring.")
    else:
        image = plot_slice(data.inner_buffer, data.outer_buffer)
        return JSONResponse(content={"image": f"data:image/png;base64,{image}"})

@app.post("/query/")
async def query(data: PlotRequest):
    lat = None
    lng = None
    radius_m = None

    if data.area:
        lng, lat = data.area.center
        radius_m = data.area.radius_m

    create_materialized_view(
        inner_buffer=data.inner_buffer or 0.0,
        outer_buffer=data.outer_buffer or 0.0,
        lat=lat,
        lng=lng,
        radius_m=radius_m,
    )
    count, df = run_query()

    df.to_pickle("latest_query.pkl")

    save_dir = Path("queries")
    save_dir.mkdir(exist_ok=True)

    # Clean values for filename (replace None with "all")
    def safe_num(val, decimals=5):
        if val is None:
            return "none"
        return str(round(val, decimals)).replace(".", "_")

    inner_str = safe_num(data.inner_buffer)
    outer_str = safe_num(data.outer_buffer)
    lat_str = safe_num(lat)
    lng_str = safe_num(lng)
    radius_str = safe_num(radius_m, 2)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"count_{count}_inner_{inner_str}_outer_{outer_str}_lat_{lat_str}_lng_{lng_str}_r_{radius_str}_{timestamp}"

    # Save as CSV
    csv_path = save_dir / f"{base_name}.csv"
    df.to_csv(csv_path, index=False)

    print(f"Query saved to: {csv_path}")

    return JSONResponse(content={
        "count": int(count),
        "csv_path": str(csv_path)
    })

@app.post("/download/")
def download():
    pkl = Path("latest_query.pkl")
    if not pkl.exists():
        raise HTTPException(status_code=400, detail="No latest_query.pkl found.")

    df = pd.read_pickle(pkl)
    if df.empty:
        raise HTTPException(status_code=400, detail="No rows found in latest_query.pkl")

    required = ["uuid", "relation_uuid", "orig_id", "relation_orig_id"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing columns: {missing}")

    # Build pairs: (fetch_id -> Mapillary image id, dest_name -> UUID)
    pairs = []
    for _, row in df.iterrows():
        if pd.notna(row["orig_id"]) and pd.notna(row["uuid"]):
            pairs.append((str(row["orig_id"]).strip(), str(row["uuid"]).strip()))
        if pd.notna(row["relation_orig_id"]) and pd.notna(row["relation_uuid"]):
            pairs.append((str(row["relation_orig_id"]).strip(), str(row["relation_uuid"]).strip()))

    if not pairs:
        raise HTTPException(status_code=400, detail="No valid image pairs found in dataframe.")

    # Perform the download
    result = download_pairs(pairs)
    return result

@app.post("/pairs/")
def get_pairs(body: dict):
    """
    Returns paginated pairs from latest_query.pkl.
    Pagination is numeric-based (cursor = row index).
    """
    limit = body.get("limit", 50)
    cursor = body.get("cursor", 0)
    
    pkl = Path("latest_query.pkl")
    if not pkl.exists():
        raise HTTPException(status_code=400, detail="No latest_query.pkl found.")

    df = pd.read_pickle(pkl)
    if df.empty:
        raise HTTPException(status_code=400, detail="No rows found in latest_query.pkl")

    required = ["uuid", "relation_uuid", "orig_id", "relation_orig_id"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"Missing columns: {missing}")

    # Check which pairs are already liked
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT uuid_1, uuid_2 FROM liked")
    liked_pairs = {(row[0], row[1]) for row in cur.fetchall()}
    con.close()

    start = int(cursor)
    end = start + int(limit)
    total = len(df)

    slice_df = df.iloc[start:end]
    items = []

    for _, row in slice_df.iterrows():
        uuid1 = row["uuid"]
        uuid2 = row["relation_uuid"]
        left = {"uuid": uuid1, "orig_id": row["orig_id"]}
        right = {"uuid": uuid2, "orig_id": row["relation_orig_id"]}
        
        # Check if this pair is liked
        is_liked = (uuid1, uuid2) in liked_pairs
        
        items.append({
            "id": f"{uuid1}|{uuid2}",
            "left": left,
            "right": right,
            "liked": is_liked,
            "distance": row.get("distance", None)
        })

    next_cursor = end if end < total else None

    return {
        "items": items,
        "total": total,
        "nextCursor": next_cursor
    }

@app.get("/image")
def get_image(uuid: str):
    """
    Serves an image from IMAGES_DIR by UUID.
    Example: /image?uuid=abcd-1234
    """
    img_path = Path(IMAGES_DIR) / f"{uuid}.jpg"
    if not img_path.exists():
        raise HTTPException(status_code=404, detail=f"Image {uuid}.jpg not found")

    return FileResponse(img_path, media_type="image/jpeg")

@app.post("/like/")
def toggle_like(data: dict):
    """
    Toggles like status for a pair.
    Expected body: {
        "id": "uuid1|uuid2",
        "liked": true/false
    }
    """
    pair_id = data.get("id")
    liked = data.get("liked", True)
    
    if not pair_id or "|" not in pair_id:
        raise HTTPException(status_code=400, detail="Invalid pair id format. Expected 'uuid1|uuid2'")
    
    uuid_1, uuid_2 = pair_id.split("|", 1)
    
    # Load the dataframe to get full pair details
    pkl = Path("latest_query.pkl")
    if not pkl.exists():
        raise HTTPException(status_code=400, detail="No latest_query.pkl found.")
    
    df = pd.read_pickle(pkl)
    
    # Find the matching row
    row = df[(df["uuid"] == uuid_1) & (df["relation_uuid"] == uuid_2)]
    
    if row.empty:
        raise HTTPException(status_code=404, detail=f"Pair {pair_id} not found in query results")
    
    row = row.iloc[0]
    orig_id_1 = row.get("orig_id")
    orig_id_2 = row.get("relation_orig_id")
    distance = row.get("distance_meters")
    
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    try:
        if liked:
            # Add like (avoid duplicates)
            cur.execute("""
                INSERT INTO liked (uuid_1, uuid_2, orig_id_1, orig_id_2, distance)
                SELECT ?, ?, ?, ?, ?
                WHERE NOT EXISTS (
                    SELECT 1 FROM liked WHERE uuid_1 = ? AND uuid_2 = ?
                )
            """, (uuid_1, uuid_2, orig_id_1, orig_id_2, distance, uuid_1, uuid_2))
        else:
            # Remove like
            cur.execute("""
                DELETE FROM liked WHERE uuid_1 = ? AND uuid_2 = ?
            """, (uuid_1, uuid_2))
        
        con.commit()
        return JSONResponse(content={"success": True, "liked": liked})
    except Exception as e:
        con.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        con.close()

@app.get("/liked/")
def get_liked():
    """
    Returns all liked pairs.
    """
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    # Check if created_at column exists
    cur.execute("PRAGMA table_info(liked)")
    columns = [row[1] for row in cur.fetchall()]
    has_created_at = "created_at" in columns
    
    if has_created_at:
        cur.execute("""
            SELECT uuid_1, uuid_2, orig_id_1, orig_id_2, distance, created_at 
            FROM liked 
            ORDER BY created_at DESC
        """)
    else:
        cur.execute("""
            SELECT uuid_1, uuid_2, orig_id_1, orig_id_2, distance 
            FROM liked
        """)
    
    rows = cur.fetchall()
    con.close()
    
    items = []
    for row in rows:
        # Handle potential bytes values
        def safe_value(val):
            if isinstance(val, bytes):
                try:
                    return val.decode('utf-8')
                except:
                    return str(val)
            return val
        
        item = {
            "uuid_1": safe_value(row[0]),
            "uuid_2": safe_value(row[1]),
            "orig_id_1": safe_value(row[2]),
            "orig_id_2": safe_value(row[3]),
            "distance": row[4] if row[4] is not None else None
        }
        if has_created_at and len(row) > 5:
            item["created_at"] = safe_value(row[5])
        items.append(item)
    
    return {"items": items, "total": len(items)}