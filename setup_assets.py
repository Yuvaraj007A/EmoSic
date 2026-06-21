import os
import urllib.request
import sys

# Define directories to create
DIRS = [
    'models',
    'haarcascade_files',
    'uploads',
    'static/css',
    'static/js',
    'static/images',
    'static/uploads',
    'static/covers',
    'static/songs'
]

# Asset URLs
HAAR_CASCADE_URL = 'https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml'
MODEL_URL = 'https://raw.githubusercontent.com/oarriaga/face_classification/master/trained_models/emotion_models/fer2013_mini_XCEPTION.102-0.66.hdf5'

# Local target paths
HAAR_PATH = 'haarcascade_files/haarcascade_frontalface_default.xml'
MODEL_PATH = 'models/mini_XCEPTION.hdf5'
AVATAR_PATH = 'static/images/default_avatar.png'

# 1x1 transparent PNG bytes for default avatar
TINY_PNG_BYTES = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'

def create_folders():
    print("Creating directory structure...")
    for d in DIRS:
        os.makedirs(d, exist_ok=True)
        print(f"  Created: {d}")

def download_file(url, path):
    if os.path.exists(path):
        print(f"File already exists: {path}")
        return

    print(f"Downloading {url} to {path}...")
    try:
        # Create user agent header to prevent HTTP 403 Forbidden errors
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req) as response, open(path, 'wb') as out_file:
            # Get content length for progress estimation
            meta = response.info()
            file_size = int(meta.get("Content-Length", 0))
            print(f"  Size: {file_size / (1024*1024):.2f} MB")
            
            downloaded = 0
            block_size = 8192
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                downloaded += len(buffer)
                out_file.write(buffer)
                
                # Dynamic percentage print
                if file_size > 0:
                    percent = downloaded * 100 / file_size
                    status = f"\r  Downloading... {percent:.2f}% [{downloaded}/{file_size} bytes]"
                    sys.stdout.write(status)
                    sys.stdout.flush()
            print("\n  Download complete!")
    except Exception as e:
        print(f"\n  Error downloading file: {e}")
        if os.path.exists(path):
            os.remove(path)

def create_default_avatar():
    if os.path.exists(AVATAR_PATH):
        print(f"Default avatar already exists at: {AVATAR_PATH}")
        return
    print(f"Creating 1x1 default avatar at: {AVATAR_PATH}")
    with open(AVATAR_PATH, 'wb') as f:
        f.write(TINY_PNG_BYTES)

if __name__ == '__main__':
    create_folders()
    download_file(HAAR_CASCADE_URL, HAAR_PATH)
    download_file(MODEL_URL, MODEL_PATH)
    create_default_avatar()
    print("Setup completed successfully!")
