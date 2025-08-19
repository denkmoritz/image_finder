import os, pandas as pd

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from utils.plot_slice import plot_slice
from utils.query import run_query
from utils.create_slice import create_materialized_view
from pathlib import Path
from utils.download import download_pairs
from config import IMAGES_DIR

from pydantic import BaseModel

class PlotRequest(BaseModel):
    inner_buffer: float
    outer_buffer: float

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
    print("Start query")
    create_materialized_view(data.inner_buffer, data.outer_buffer)
    count, df = run_query()
    df.to_pickle("latest_query.pkl")
    return JSONResponse(content={"count": count})

@app.post("/download/")
def download(limit_pairs: int = 10):
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

    # only first N pairs
    df = df.head(limit_pairs)

    # build (fetch_id, dest_uuid) pairs for both sides
    pairs = []
    for _, r in df.iterrows():
        if pd.notna(r["orig_id"]) and pd.notna(r["uuid"]):
            pairs.append((str(r["orig_id"]), str(r["uuid"])))
        if pd.notna(r["relation_orig_id"]) and pd.notna(r["relation_uuid"]):
            pairs.append((str(r["relation_orig_id"]), str(r["relation_uuid"])))

    stats = download_pairs(pairs)

    # include locations for the gallery
    loc_cols = [c for c in ("uuid","relation_uuid","lat_1","lon_1","lat_2","lon_2","relation_id") if c in df.columns]
    locations = df[loc_cols].to_dict(orient="records") if loc_cols else []

    return JSONResponse(content={
        "message": "Download completed",
        **stats,
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