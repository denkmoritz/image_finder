import os, pandas as pd, json

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from utils.plot_slice import plot_slice
from utils.query import run_query
from utils.create_slice import create_materialized_view
from utils.download import *
from utils.filtering import *

from config import (MAX_DISTANCE_M, MAX_ANGLE_DEG, PHASH_THRESHOLD, DROP_SINGLETONS)

from pydantic import BaseModel

class PlotRequest(BaseModel):
    inner_buffer: float
    outer_buffer: float

GROUPS_PATH = "latest_groups.json"
PICKLE_PATH = "latest_query.pkl"

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
    image = plot_slice(data.inner_buffer, data.outer_buffer)
    return JSONResponse(content={"image": f"data:image/png;base64,{image}"})

@app.post("/query/")
async def query(data: PlotRequest):
    # 1) DB slice / materialized view
    create_materialized_view(data.inner_buffer, data.outer_buffer)

    # 2) Run core SQL
    count, df = run_query()

    # 3) Keep a copy for debugging
    df.to_pickle(PICKLE_PATH)

    # 4) Geo/heading precluster (connected components)
    geo_groups = precluster_from_df(
        df,
        max_distance_m=MAX_DISTANCE_M,
        max_angle_deg=MAX_ANGLE_DEG
    )

    # 5) Persist groups (optional, for later inspection)
    with open(GROUPS_PATH, "w", encoding="utf-8") as f:
        json.dump(geo_groups, f)

    # 6) Flatten to unique local UUIDs we’ll want thumbnails for
    unique_ids = sorted({uid for group in geo_groups for uid in group})

    # 7) Build local->Mapillary ID map from BOTH sides of the pair (uuid & relation_uuid)
    #    so we can fetch thumbs for any ID that appears in geo_groups.
    a_map = (
        df[["uuid", "orig_id"]]
        .dropna()
        .astype(str)
        .drop_duplicates(subset=["uuid"])
        .set_index("uuid")["orig_id"]
        .to_dict()
    )
    b_map = (
        df[["relation_uuid", "relation_orig_id"]]
        .dropna()
        .astype(str)
        .drop_duplicates(subset=["relation_uuid"])
        .set_index("relation_uuid")["relation_orig_id"]
        .to_dict()
    )
    id_map = {**a_map, **b_map}  # {local_uuid: orig_id}

    # 8) Download thumbs (async, cached) — pass Mapillary IDs, not local uuids
    ok_mapillary_ids = await download_all(id_map.values(), variant="thumb_256")

    # 9) Build {uuid: local_thumb_path} only for ones we downloaded successfully
    ok_ids = {uuid for uuid, mid in id_map.items() if mid in ok_mapillary_ids and uuid in unique_ids}
    thumb_paths = build_thumb_paths(ok_ids, variant="thumb_256")

    # 10) Visual de-dup (pHash) within each geo group → keep 1 per visual subgroup
    final_ids, report = dedupe_groups_by_phash(
        geo_groups,
        thumb_paths,
        phash_threshold=PHASH_THRESHOLD,
        drop_singletons=DROP_SINGLETONS
    )

    # 11) Respond with useful counts + results
    return JSONResponse(content={
        "count_pairs": count,
        "count_geo_groups": len(geo_groups),
        "count_unique_ids": len(unique_ids),
        "count_thumbs_available": len(thumb_paths),
        "count_final_ids": len(final_ids),
        "unique_ids": unique_ids,
        "final_ids": sorted(final_ids),
        # "report": report,  # uncomment if you want detailed clustering info
    })

@app.post("/download/")
async def download():
    if not os.path.exists("latest_query.pkl"):
        return JSONResponse(status_code=400, content={"error": "No query data found. Run /query/ first."})

    df = pd.read_pickle("latest_query.pkl")
    df = df[df['source'] == 'Mapillary'].drop_duplicates(subset=['relation_id']).reset_index(drop=True)

    selected = []
    #for _, row in df.iterrows():
     #   if len(selected) >= 10:
      #      break
       # if not selected or is_far_enough(row, pd.DataFrame(selected), min_distance=2, min_heading_diff=5):
        #    selected.append(row)

    #if not selected:
     #   return JSONResponse(status_code=400, content={"error": "No suitable pairs found"})

    limited_df = pd.DataFrame(selected)

    download_all(limited_df)

    locations = limited_df[['uuid', 'relation_uuid', 'lat_1', 'lon_1', 'lat_2', 'lon_2', 'relation_id']].to_dict(orient='records')

    return JSONResponse(content={
        "message": "Download completed",
        "locations": locations
    })

@app.get("/image/{image_id}")
async def get_image(image_id: str):
    image_path = os.path.join("berlin_images", f"{image_id}.jpeg")
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(image_path, media_type="image/jpeg")