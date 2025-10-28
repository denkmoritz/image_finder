import pandas as pd
from utils.db import get_db_connection

def run_query(city):
    # Validate city and get EPSG code
    city_epsg = {
        "berlin": 32633,
        "paris": 32631,
        "washington": 32618,
        "singapore": 32648
    }
    
    city = city.lower()
    if city not in city_epsg:
        raise ValueError(f"Invalid city '{city}'. Must be one of: {list(city_epsg.keys())}")
    
    epsg = city_epsg[city]
    
    # Dynamic table and view names based on city
    view_name = f"{city}_slice"
    table_name = city
    
    QUERY = f"""
    WITH high_q AS (
        SELECT *
        FROM {table_name}
        WHERE mly_quality_score >= 0.95
    )
    SELECT
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
        a.geometry_comp_{epsg} <-> b.geometry_comp_{epsg} AS distance_meters,
        a.source_x          AS source,
        CONCAT(a.uuid, '__', b.uuid) AS relation_id
    FROM {view_name} AS a
    JOIN high_q AS b
    ON  b.uuid > a.uuid
        AND b.geometry_comp_{epsg} && a.slice_geom
        AND ST_Within(b.geometry_comp_{epsg}, a.slice_geom)
        AND LEAST(
            ABS(a.heading - b.heading),
            360 - ABS(a.heading - b.heading)
            ) <= 45;"""
    
    engine = get_db_connection()
    with engine.connect() as conn:
        df = pd.read_sql_query(QUERY, conn)
    
    return df.shape[0], df