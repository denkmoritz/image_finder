import os
import time
import random
import threading
import urllib
from pathlib import Path

import pandas as pd
import mapillary.interface as mly


# CONFIGURATION
ACCESS_TOKEN = 'MLY|9589650211070406|360124f70ee4d3f32da7987da0ae45b0'
INPUT_CSV = '...'
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
        with urllib.request.urlopen(image_url) as web_file:
            data = web_file.read()
            with open(dst_path, mode='wb') as local_file:
                local_file.write(data)
    except Exception as e:
        print(f"[ERROR] Download failed for {image_url}: {e}")


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

    for _, row in df.iterrows():
        uuid = row['uuid']
        image_id = row['orig_id']
        dst_path = os.path.join(out_folder, f"{uuid}.jpeg")

        if os.path.isfile(dst_path):
            continue

        t = threading.Thread(target=download_mapillary_image, args=(image_id, dst_path))
        threads.append(t)
        counter += 1

        if counter % NUM_THREADS == 0:
            for thread in threads:
                thread.setDaemon(True)
                thread.start()
            for thread in threads:
                thread.join()
            threads = []

    for thread in threads:
        thread.setDaemon(True)
        thread.start()
    for thread in threads:
        thread.join()


def retry_missing(df_all, out_folder):
    while True:
        print("\nChecking for missing images...")
        missing = []

        for _, row in df_all.iterrows():
            uuid = row['uuid']
            image_path = os.path.join(out_folder, f"{uuid}.jpeg")
            if not os.path.isfile(image_path):
                missing.append(row)

        if not missing:
            print("All images downloaded.")
            break

        print(f"Retrying {len(missing)} missing images...")
        retry_df = pd.DataFrame(missing)
        download_batch(retry_df, out_folder)
        time.sleep(RETRY_WAIT)


def main():
    set_token()

    df_all = pd.read_csv(INPUT_CSV).reset_index(drop=True)
    df_all = df_all[df_all['source'] == 'Mapillary']
    csv_name = Path(INPUT_CSV).stem
    out_folder = f'./sample_output/{csv_name}_images'
    Path(out_folder).mkdir(parents=True, exist_ok=True)

    print(f"Total Mapillary images: {len(df_all)}")
    print("Starting download...")

    download_batch(df_all, out_folder)
    retry_missing(df_all, out_folder)

    print("Download process completed.")


if __name__ == '__main__':
    main()