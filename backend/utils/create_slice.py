from utils.db import get_db_connection


def create_materialized_view(inner_buffer, outer_buffer):
    assert isinstance(inner_buffer, (int, float)) and isinstance(outer_buffer, (int, float)), \
    "Buffer distances must be numeric"

    query = f"""
    DROP MATERIALIZED VIEW IF EXISTS berlin_slice;

    CREATE MATERIALIZED VIEW berlin_slice AS
    SELECT
        uuid,
        orig_id_x,
        view_direction,
        platform,
        place,
        source_x,
        heading,
        geometry_comp_32633,
        ST_Difference(
            ST_Difference(
                ST_Buffer(geometry_comp_32633, {outer_buffer}),
                ST_Buffer(geometry_comp_32633, {inner_buffer})
            ),
            ST_Buffer(
                ST_MakeLine(
                    ST_SetSRID(
                        ST_MakePoint(
                            ST_X(geometry_comp_32633)+{outer_buffer}*SIN(RADIANS(heading)),
                            ST_Y(geometry_comp_32633)+{outer_buffer}*COS(RADIANS(heading))
                        ), 32633),
                    ST_SetSRID(
                        ST_MakePoint(
                            ST_X(geometry_comp_32633)-{outer_buffer}*SIN(RADIANS(heading)),
                            ST_Y(geometry_comp_32633)-{outer_buffer}*COS(RADIANS(heading))
                        ), 32633)
                ),
                {inner_buffer}, 'endcap=square join=mitre'
            )
        ) AS slice_geom
    FROM berlin
    WHERE mly_quality_score >= 0.95;

    DROP INDEX IF EXISTS berlin_slice_gist;
    CREATE INDEX berlin_slice_gist ON berlin_slice USING gist (slice_geom);
    """

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(query)
        conn.commit()
        print("Materialized view 'berlin_slice' created successfully.")
    finally:
        conn.close()


if __name__ == '__main__':
    create_materialized_view(inner_buffer=8, outer_buffer=12)