import os, pandas as pd

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from utils.plot_slice import plot_slice
from utils.query import run_query
from utils.create_slice import create_materialized_view
from utils.download import download_all
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

app.post("/query/")
async def query(data: PlotRequest):
    create_materialized_view(data.inner_buffer, data.outer_buffer)
    count, df = run_query()
    df.to_pickle("latest_query.pkl")
    return JSONResponse(content={count: count})


@app.post("/download/")
async def download():
    if not os.path.exists("latest_query.pkl"):
        return JSONResponse(status_code=400, content={"error": "No query data found. Run /query/ first."})

    df = pd.read_pickle("latest_query.pkl")
    download_all(df)

    return JSONResponse(content={"message": "Download initiated"})