import os
import urllib.request
import zipfile
import tarfile
from tqdm import tqdm

class DownloadProgressBar(tqdm):
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)

def download_url(url, output_path):
    print(f"Downloading {url} to {output_path}...")
    with DownloadProgressBar(unit='B', unit_scale=True, miniters=1, desc=url.split('/')[-1]) as t:
        urllib.request.urlretrieve(url, filename=output_path, reporthook=t.update_to)
    print("Download complete.")

def extract_file(filepath, extract_dir):
    print(f"Extracting {filepath}...")
    if filepath.endswith('.zip'):
        with zipfile.ZipFile(filepath, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
    elif filepath.endswith('.tar.gz') or filepath.endswith('.tgz'):
        with tarfile.open(filepath, 'r:gz') as tar_ref:
            tar_ref.extractall(extract_dir)
    elif filepath.endswith('.tar'):
        with tarfile.open(filepath, 'r:') as tar_ref:
            tar_ref.extractall(extract_dir)
    print("Extraction complete.")

if __name__ == "__main__":
    DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'training', 'data')
    os.makedirs(DATA_DIR, exist_ok=True)

    # 300W-LP typically comes in a massive zip from academic drives. 
    # For automated scripts without Google Drive API authentication, 
    # it's common to use a public mirror or request users to download manually if it's walled behind a form.
    # We will simulate the download here with a placeholder URL, 
    # but the Colab notebook will contain instructions for authenticating with Google Drive to pull the real dataset.
    print("NOTE: 300W-LP is heavily restricted and usually requires form submission.")
    print("This script provides the scaffolding to download/extract once you have the public mirror URL.")
    
    # Placeholder mirror for 300W-LP (users must replace with valid direct link)
    DATASET_URL = "https://example.com/300W_LP.zip"
    DEST_ZIP = os.path.join(DATA_DIR, "300W_LP.zip")
    
    # download_url(DATASET_URL, DEST_ZIP)
    # extract_file(DEST_ZIP, DATA_DIR)
    
    print("Please use the Colab notebook to download the dataset seamlessly via gdown.")
