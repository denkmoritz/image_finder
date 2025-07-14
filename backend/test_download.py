import pandas as pd
from utils.download import download_all

if __name__ == "__main__":
    print("Starting test download...")
    df = pd.read_pickle("latest_query.pkl")
    download_all(df[:2])
    print("Test completed.")
