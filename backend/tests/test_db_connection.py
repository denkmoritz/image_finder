from utils.db import get_db_connection
import pandas as pd


QUERY = """SELECT Count(*) FROM berlin LIMIT 1;"""
if __name__ == "__main__":
    
    engine = get_db_connection()
    with engine.connect() as conn:
        df = pd.read_sql_query(QUERY, conn)
    
    print(df.head())