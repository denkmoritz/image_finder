from __future__ import annotations
import os
from typing import Dict, Iterable, List, Tuple, Set
import pandas as pd
from PIL import Image
import imagehash

# ------------------ helpers ------------------

def heading_diff(h1: float, h2: float) -> float:
    d = abs((h1 - h2) % 360.0)
    return min(d, 360.0 - d)

a.uuid              AS uuid,
    b.uuid              AS relation_uuid,
    a.orig_id_x         AS orig_id,
    b.orig_id_x         AS relation_orig_id,
    a.heading           AS h_1,
    b.heading           AS h_2,
    a.comp_lon          AS lon_1,
    b.comp_lon          AS lon_2,
    a.comp_lat          AS lat_1,
    b.comp_lat          AS lat_2,
    a.source_x          AS source,
    CONCAT(a.uuid, '__', b.uuid) AS relation_pair