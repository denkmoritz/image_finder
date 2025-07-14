import os
import time
import random
import threading
import requests
from pathlib import Path

import pandas as pd
import mapillary.interface as mly


# CONFIGURATION
ACCESS_TOKEN = 'MLY|9589650211070406|360124f70ee4d3f32da7987da0ae45b0'
NUM_THREADS = 100
RETRY_WAIT = 3


def set_token():
    mly.set_access_token(ACCESS_TOKEN)


def get_image_url(image_id):
    """Get the download URL for a Mapillary image."""
    try:
        time.sleep(random.uniform(0.1, 1.0))
        return mly.image_thumbnail(image_id, 2048)
    except Exception as e:
        print(f"[ERROR] Failed to get URL for image {image_id}: {e}")
        return None


def download_image_from_url(image_url, dst_path):
    try:
        response = requests.get(image_url, stream=True, timeout=10)
        response.raise_for_status()
        with open(dst_path, 'wb') as local_file:
            for chunk in response.iter_content(chunk_size=8192):
                local_file.write(chunk)
    except requests.exceptions.RequestException as e:
        print(f'[ERROR] Download failed for {image_url}: {e}')


def download_mapillary_image(image_id, dst_path):
    image_url = get_image_url(image_id)
    if image_url:
        download_image_from_url(image_url, dst_path)


def already_downloaded_ids(folder_path):
    return {f.split('.')[0] for f in os.listdir(folder_path) if f.endswith('.jpeg')}


def download_batch(df, out_folder):
    os.makedirs(out_folder, exist_ok=True)
    threads = []
    counter = 0

    def download_pair(row):
        id_1, uuid_1 = row['orig_id'], row['uuid']
        id_2, uuid_2 = row['relation_orig_id'], row['relation_uuid']

        dst_path_1 = os.path.join(out_folder, f"{uuid_1}.jpeg")
        dst_path_2 = os.path.join(out_folder, f"{uuid_2}.jpeg")

        if not os.path.isfile(dst_path_1):
            download_mapillary_image(id_1, dst_path_1)

        if not os.path.isfile(dst_path_2):
            download_mapillary_image(id_2, dst_path_2)

    for _, row in df.iterrows():
        t = threading.Thread(target=download_pair, args=(row,))
        t.daemon = True
        threads.append(t)
        counter += 1

        if counter % NUM_THREADS == 0:
            print(f"Downloading batch of {NUM_THREADS} image pairs...")
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            threads = []

    if threads:
        print(f"Downloading final batch of {len(threads)} image pairs...")
        for t in threads:
            t.start()
        for t in threads:
            t.join()

def retry_missing(df_all, out_folder):
    while True:
        print("\nChecking for missing image pairs...")
        missing = []

        for _, row in df_all.iterrows():
            uuid_1 = row['uuid']
            uuid_2 = row['relation_uuid']
            path_1 = os.path.join(out_folder, f"{uuid_1}.jpeg")
            path_2 = os.path.join(out_folder, f"{uuid_2}.jpeg")

            if not os.path.isfile(path_1) or not os.path.isfile(path_2):
                missing.append(row)

        if not missing:
            print("All image pairs downloaded.")
            break

        print(f"Retrying {len(missing)} missing image pairs...")
        retry_df = pd.DataFrame(missing)
        download_batch(retry_df, out_folder)
        time.sleep(RETRY_WAIT)

def download_all(df):
    set_token()
    df_all = df[df['source'] == 'Mapillary'].reset_index(drop=True)

    out_folder = './berlin_images/'
    Path(out_folder).mkdir(parents=True, exist_ok=True)

    print(f"Total Mapillary image pairs: {len(df_all)}")
    print("Starting download...")

    download_batch(df_all, out_folder)
    retry_missing(df_all, out_folder)

    print("Download process completed.")