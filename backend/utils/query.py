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
    a.view_direction    AS v_1,
    b.view_direction    AS v_2,
    a.platform          AS p_1,
    b.platform          AS p_2,
    a.heading           AS h_1,
    b.heading           AS h_2,
    a.place             AS place_1,
    b.place             AS place_2,
    ST_Distance(a.geometry_comp_32633, b.geometry_comp_32633) AS distance_meters,
    a.source_x          AS source
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
    conn = get_db_connection()
    try:
        df = pd.read_sql_query(QUERY, conn)

        uuid_df = df[['uuid', 'orig_id', 'source']].rename(columns={'uuid': 'uuid'})

        relation_df = df[['relation_uuid', 'relation_orig_id', 'source']].rename(
            columns={'relation_uuid': 'uuid', 'relation_orig_id': 'orig_id'})

        combined_df = pd.concat([uuid_df, relation_df], ignore_index=True).drop_duplicates()

        return combined_df.shape[0], combined_df
    
    finally:
        conn.close()


if __name__ == '__main__':
    df_result = run_query()
    print(df_result.head())