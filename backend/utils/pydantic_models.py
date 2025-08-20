from pydantic import BaseModel, Field
from typing import Optional

class PairsRequest(BaseModel):
    limit: int = Field(default=50, ge=1, le=200)
    cursor: Optional[str] = None
    user_id: str = "default"

class InteractionItem(BaseModel):
    pairId: str
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    seen: Optional[bool] = None
    starred: Optional[bool] = None
    userId: str = "default"

class PlotRequest(BaseModel):
    inner_buffer: float
    outer_buffer: float


class DownloadRequest(BaseModel):
    limit_pairs: int = 50
    cursor: Optional[str] = None
    all: bool = False
    include_locations: bool = False