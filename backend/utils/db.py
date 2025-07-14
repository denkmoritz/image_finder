from sqlalchemy import create_engine
from config import Config

def get_db_connection():
    url = f"postgresql+psycopg://{Config.DB_USER}:{Config.DB_PASSWORD}@{Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME}"
    engine = create_engine(url)
    return engine