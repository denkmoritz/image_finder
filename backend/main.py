import os, pandas as pd

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from utils.plot_slice import plot_slice
from utils.query import run_query
from utils.create_slice import create_materialized_view
from utils.download import download_all

from pydantic import BaseModel
from geopy.distance import geodesic

class PlotRequest(BaseModel):
    inner_buffer: float
    outer_buffer: float


def heading_diff(h1, h2):
    return min(abs(h1 - h2), 360 - abs(h1 - h2))

def is_far_enough(new_row, selected_rows, min_distance=3, min_heading_diff=5):
    new_center = ((new_row['lat_1'] + new_row['lat_2']) / 2,
                  (new_row['lon_1'] + new_row['lon_2']) / 2)
    new_heading = (new_row['h_1'] + new_row['h_2']) / 2

    for _, row in selected_rows.iterrows():
        existing_center = ((row['lat_1'] + row['lat_2']) / 2,
                           (row['lon_1'] + row['lon_2']) / 2)
        existing_heading = (row['h_1'] + row['h_2']) / 2
        
        if heading_diff(new_heading, existing_heading) < min_heading_diff:
            return False
        
        if geodesic(new_center, existing_center).meters < min_distance:
            return False

    return True

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
async def download():
    if not os.path.exists("latest_query.pkl"):
        return JSONResponse(status_code=400, content={"error": "No query data found. Run /query/ first."})

    df = pd.read_pickle("latest_query.pkl")
    df = df[df['source'] == 'Mapillary'].drop_duplicates(subset=['relation_id']).reset_index(drop=True)

    selected = []
    for _, row in df.iterrows():
        if len(selected) >= 10:
            break
        if not selected or is_far_enough(row, pd.DataFrame(selected), min_distance=2, min_heading_diff=5):
            selected.append(row)

    if not selected:
        return JSONResponse(status_code=400, content={"error": "No suitable pairs found"})

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