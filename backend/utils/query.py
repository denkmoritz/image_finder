import pandas as pd
from utils.db import get_db_connection

QUERY = """
WITH high_q AS (
    SELECT *
    FROM berlin
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
    a.geometry_comp_32633 <-> b.geometry_comp_32633 AS distance_meters,
    a.source_x          AS source,
    CONCAT(a.uuid, '__', b.uuid) AS relation_id
FROM berlin_slice AS a
JOIN high_q AS b
ON  b.uuid > a.uuid
    AND b.geometry_comp_32633 && a.slice_geom
    AND ST_Within(b.geometry_comp_32633, a.slice_geom)
    AND LEAST(
        ABS(a.heading - b.heading),
        360 - ABS(a.heading - b.heading)
        ) <= 45;"""

def run_query():
    engine = get_db_connection()
    with engine.connect() as conn:
        df = pd.read_sql_query(QUERY, conn)
        return df.shape[0], df

if __name__ == '__main__':
    df_result = run_query()
    print(df_result.head())