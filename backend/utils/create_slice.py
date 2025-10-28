from utils.db import get_db_connection
from sqlalchemy import text

def create_materialized_view(city, inner_buffer, outer_buffer, lat=None, lng=None, radius_m=None):
    assert isinstance(inner_buffer, (int, float)) and isinstance(outer_buffer, (int, float)), \
        "Buffer distances must be numeric"
    
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
    
    area_filter = ""
    if lat is not None and lng is not None and radius_m is not None:
        area_filter = f"""
            AND ST_Intersects(
                geometry_comp_{epsg},
                ST_Transform(
                    ST_Buffer(
                        ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326)::geography,
                        {radius_m}
                    )::geometry,
                    {epsg}
                )
            )
        """
    
    # Dynamic view and table names based on city
    view_name = f"{city}_slice"
    table_name = city
    index_name = f"{city}_slice_gist"
    
    query = f"""
    DROP MATERIALIZED VIEW IF EXISTS {view_name};
    CREATE MATERIALIZED VIEW {view_name} AS
    SELECT
        uuid,
        orig_id_x,
        view_direction,
        platform,
        place,
        source_x,
        heading,
        geometry_comp_{epsg},
        comp_lat,
        comp_lon,
        ST_Difference(
            ST_Difference(
                ST_Buffer(geometry_comp_{epsg}, {outer_buffer}),
                ST_Buffer(geometry_comp_{epsg}, {inner_buffer})
            ),
            ST_Buffer(
                ST_MakeLine(
                    ST_SetSRID(
                        ST_MakePoint(
                            ST_X(geometry_comp_{epsg})+{outer_buffer}*SIN(RADIANS(heading)),
                            ST_Y(geometry_comp_{epsg})+{outer_buffer}*COS(RADIANS(heading))
                        ), {epsg}),
                    ST_SetSRID(
                        ST_MakePoint(
                            ST_X(geometry_comp_{epsg})-{outer_buffer}*SIN(RADIANS(heading)),
                            ST_Y(geometry_comp_{epsg})-{outer_buffer}*COS(RADIANS(heading))
                        ), {epsg})
                ),
                {inner_buffer}, 'endcap=square join=mitre'
            )
        ) AS slice_geom
    FROM {table_name}
    WHERE mly_quality_score >= 0.95
    {area_filter};
    
    DROP INDEX IF EXISTS {index_name};
    CREATE INDEX {index_name} ON {view_name} USING gist (slice_geom);
    """
    
    engine = get_db_connection()
    with engine.begin() as connection:
        connection.execute(text(query))
    
    print(f"Materialized view '{view_name}' created successfully for {city}.")