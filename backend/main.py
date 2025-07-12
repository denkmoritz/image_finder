from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

from utils.plot_slice import plot_slice
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