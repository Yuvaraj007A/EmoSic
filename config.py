import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'default_secret_key_123456')
    MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/emotion_music_db')
    
    # Path configuration
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    COVER_FOLDER = os.path.join(BASE_DIR, 'static', 'covers')
    SONG_FOLDER = os.path.join(BASE_DIR, 'static', 'songs')
    
    HAAR_CASCADE_PATH = os.path.join(BASE_DIR, 'haarcascade_files', 'haarcascade_frontalface_default.xml')
    MODEL_PATH = os.path.join(BASE_DIR, 'models', 'mini_XCEPTION.hdf5')
    
    # Session options
    SESSION_COOKIE_HTTPONLY = True
    # Hugging Face Spaces run inside iframes, requiring SameSite=None and Secure=True to persist cookies
    IS_HF = 'SPACE_ID' in os.environ
    SESSION_COOKIE_SECURE = IS_HF
    SESSION_COOKIE_SAMESITE = 'None' if IS_HF else 'Lax'
    
    # Upload parameters
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB limit
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    ALLOWED_AUDIO_EXTENSIONS = {'mp3', 'wav', 'ogg'}

    @staticmethod
    def allowed_file(filename, allowed_extensions):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions
