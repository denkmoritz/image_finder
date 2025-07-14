from utils.db import get_db_connection
from sqlalchemy import text

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
        comp_lat,
        comp_lon,
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

    engine = get_db_connection()

    with engine.begin() as connection:
        connection.execute(text(query))
        print("Materialized view 'berlin_slice' created successfully.")