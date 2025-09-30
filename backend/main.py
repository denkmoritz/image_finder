import pandas as pd
from pathlib import Path
from datetime import datetime
import re

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

    #df_parameters = pd.DataFrame([{
     #   "lng": lng,
      #  "lat": lat,
       # "radius_m": radius_m
    #}])
    #df_parameters.to_pickle("latest_parameters.pkl")

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
def download(req: DownloadRequest):
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

    total = int(len(df))

    # compute slice
    if req.all:
        offset = 0
        end = total
        next_cursor = None
        df_slice = df
    else:
        offset = 0
        if req.cursor:
            try:
                offset = int(b64dec(req.cursor).get("offset", 0))
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid cursor")
        end = min(offset + req.limit_pairs, total)
        next_cursor = None if end >= total else b64enc({"offset": end})
        df_slice = df.iloc[offset:end].copy()

    # (fetch_id, dest_uuid) list for download_pairs()
    pairs: List[tuple] = []
    for _, r in df_slice.iterrows():
        if pd.notna(r["orig_id"]) and pd.notna(r["uuid"]):
            pairs.append((str(r["orig_id"]), str(r["uuid"])))
        if pd.notna(r["relation_orig_id"]) and pd.notna(r["relation_uuid"]):
            pairs.append((str(r["relation_orig_id"]), str(r["relation_uuid"])))

    # de-dup in case any UUIDs repeat
    pairs = list(dict.fromkeys(pairs))

    stats = download_pairs(pairs)

    # include locations if requested (only for this slice)
    locations = []
    if req.include_locations:
        loc_cols = [c for c in ("uuid","relation_uuid","lat_1","lon_1","lat_2","lon_2","relation_id") if c in df_slice.columns]
        locations = df_slice[loc_cols].to_dict(orient="records") if loc_cols else []

    return JSONResponse(content={
        "message": "Download completed",
        **stats,
        "attempted_files": len(pairs),
        "slice": {"start": offset, "end": end, "count": end - offset},
        "total_pairs": total,
        "nextCursor": next_cursor,
        "locations": locations
    })

@app.get("/image/{uuid}")
def get_image(uuid: str):
    """
    Serve the downloaded image by UUID, regardless of extension.
    Frontend uses: http://localhost:8000/image/<uuid>
    """
    base = IMAGES_DIR / uuid
    for ext, mime in ((".jpg","image/jpeg"), (".jpeg","image/jpeg"), (".png","image/png"), (".webp","image/webp")):
        p = base.with_suffix(ext)
        if p.exists() and p.stat().st_size > 0:
            return FileResponse(str(p), media_type=mime)
    raise HTTPException(status_code=404, detail=f"Image {uuid} not found")

@app.post("/pairs")
def pairs(req: PairsRequest):
    if not PKL_PATH.exists():
        raise HTTPException(status_code=400, detail="No latest_query.pkl found. Run /query first.")
    df = pd.read_pickle(PKL_PATH)
    total = int(len(df))

    # compute offset from cursor
    offset = 0
    if req.cursor:
        try:
            offset = int(b64dec(req.cursor).get("offset", 0))
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid cursor")

    # slice page
    end = min(offset + req.limit, total)
    page = df.iloc[offset:end].copy()

    # sanity check
    need = ["uuid","relation_uuid","lat_1","lon_1","lat_2","lon_2","orig_id","relation_orig_id"]
    for c in need:
        if c not in page.columns:
            raise HTTPException(status_code=400, detail=f"Missing column '{c}' in latest_query.pkl")

    # 1) prepare download pairs (orig_id -> uuid, relation_orig_id -> relation_uuid)
    dl_pairs: list[tuple[str,str]] = []
    for _, r in page.iterrows():
        if pd.notna(r["orig_id"]) and pd.notna(r["uuid"]):
            dl_pairs.append((str(r["orig_id"]), str(r["uuid"])))
        if pd.notna(r["relation_orig_id"]) and pd.notna(r["relation_uuid"]):
            dl_pairs.append((str(r["relation_orig_id"]), str(r["relation_uuid"])))
    dl_pairs = list(dict.fromkeys(dl_pairs))  # dedupe

    # 2) trigger download for this slice (lazy: only new ones are fetched)
    stats = download_pairs(dl_pairs)

    # 3) build items with correct URLs
    items = []
    pair_ids = []
    for _, r in page.iterrows():
        u1 = str(r["uuid"]); u2 = str(r["relation_uuid"])
        pid = make_pair_id(u1, u2)
        pair_ids.append(pid)
        items.append({
            "id": pid,
            "left": {
                "src": f"http://localhost:8000/image/{u1}",
                "lat": float(r["lat_1"]), "lng": float(r["lon_1"]),
            },
            "right": {
                "src": f"http://localhost:8000/image/{u2}",
                "lat": float(r["lat_2"]), "lng": float(r["lon_2"]),
            },
        })

    # hydrate with interactions
    imap = fetch_interactions_map(pair_ids)
    for it in items:
        meta = imap.get(it["id"], {})
        it["rating"]  = meta.get("rating")
        it["seen"]    = meta.get("seen", False)
        it["starred"] = meta.get("starred", False)

    next_cursor = None if end >= total else b64enc({"offset": end})

    return JSONResponse(content={
        "items": items,
        "total": total,
        "nextCursor": next_cursor,
        "download_stats": stats,
    })

@app.post("/interactions")
def interactions(payload: List[InteractionItem]):
    if not payload:
        return JSONResponse(content={"ok": True, "updated": 0})

    updated = 0
    for it in payload:
        # permit "clear rating" by omitting rating or sending null; seen defaults to True on explicit rating
        seen = it.seen
        if seen is None and it.rating is not None:
            seen = True
        upsert_interaction(
            pair_id=it.pairId,
            rating=it.rating,
            seen=seen,
            starred=it.starred
        )
        updated += 1

    return JSONResponse(content={"ok": True, "updated": updated})

# @app.get("/progress")
# def progress(user_id: str = "default"):
#     if not PKL_PATH.exists():
#         raise HTTPException(status_code=400, detail="No latest_query.pkl found. Run /query first.")
#     df = pd.read_pickle(PKL_PATH)
#     total = int(len(df))

#     # compute current set of pair_ids
#     if total == 0:
#         return JSONResponse(content={"total": 0, "reviewed": 0, "rated": 0, "seen": 0, "starred": 0})

#     pair_ids = [make_pair_id(str(r["uuid"]), str(r["relation_uuid"])) for _, r in df.iterrows()]

#     con = sqlite3.connect(DB_PATH)
#     cur = con.cursor()
#     qmarks = ",".join("?" for _ in pair_ids)
#     cur.execute(f"""
#         SELECT
#           SUM(CASE WHEN rating IS NOT NULL OR seen=1 THEN 1 ELSE 0 END) AS reviewed,
#           SUM(CASE WHEN rating IS NOT NULL THEN 1 ELSE 0 END) AS rated,
#           SUM(CASE WHEN seen=1 THEN 1 ELSE 0 END) AS seen,
#           SUM(CASE WHEN starred=1 THEN 1 ELSE 0 END) AS starred
#         FROM interactions
#         WHERE pair_id IN ({qmarks})
#     """, (pair_ids))
#     row = cur.fetchone()
#     con.close()

#     reviewed = int(row[0] or 0)
#     rated = int(row[1] or 0)
#     seen = int(row[2] or 0)
#     starred = int(row[3] or 0)

#     return JSONResponse(content={
#         "total": total,
#         "reviewed": reviewed,
#         "rated": rated,
#         "seen": seen,
#         "starred": starred
#     })

@app.post("/export-likes/")
async def export_likes(data: LikeExportRequest):
    lat, lng, radius_m = None, None, None
    if data.area:
        lng, lat = data.area.get("center", (None, None))
        radius_m = data.area.get("radius_m", None)

    likes = data.likes
    like_count = len(likes)
    if like_count == 0:
        return JSONResponse(content={"error": "No likes to export"}, status_code=400)

    # Convert likes to DataFrame
    df = pd.DataFrame(likes)

    # Save directory
    save_dir = Path("likes")
    save_dir.mkdir(exist_ok=True)

    # Safe filename (reuse your query logic)
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

    base_name = f"likes_{like_count}_inner_{inner_str}_outer_{outer_str}_lat_{lat_str}_lng_{lng_str}_r_{radius_str}_{timestamp}"
    csv_path = save_dir / f"{base_name}.csv"

    df.to_csv(csv_path, index=False)

    print(f"Liked pairs saved to: {csv_path}")

    return JSONResponse(content={"csv_path": str(csv_path)})

app.mount("/likes", StaticFiles(directory="likes"), name="likes")

@app.get("/list-likes/")
async def list_likes():
    save_dir = Path("likes")
    if not save_dir.exists():
        return JSONResponse(content={"likes": []})

    files = list(save_dir.glob("*.csv"))
    likes_list = []

    for file in files:
        # Flexible regex to capture numbers with underscores or 'none'
        pattern = (
            r"likes_(\d+)_inner_([0-9_]+|none)_outer_([0-9_]+|none)_"
            r"lat_([0-9_]+|none)_lng_([0-9_\-]+|none)_r_([0-9_]+|none)_(\d{8}_\d{6})\.csv"
        )
        match = re.match(pattern, file.name)
        if match:
            like_count, inner, outer, lat, lng, radius, timestamp = match.groups()
            # Convert underscores back to decimal points where possible
            def decode_num(val):
                if val == "none":
                    return None
                return val.replace("_", ".")
            
            likes_list.append({
                "file_name": file.name,
                "like_count": int(like_count),
                "inner_buffer": decode_num(inner),
                "outer_buffer": decode_num(outer),
                "lat": decode_num(lat),
                "lng": decode_num(lng),
                "radius_m": decode_num(radius),
                "timestamp": timestamp
            })

    # Sort by newest first
    likes_list.sort(key=lambda x: x["timestamp"], reverse=True)
    return JSONResponse(content={"likes": likes_list})