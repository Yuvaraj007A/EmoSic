import os
import sys
import io
import re
import cv2
import base64
import random
import datetime
from bson.objectid import ObjectId
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_from_directory
import numpy as np
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import Config

# Initialize Keras/TensorFlow flag
MODEL_LOADED = False
emotion_model = None

try:
    import tensorflow as tf
    from tensorflow.keras.models import load_model
    if os.path.exists(Config.MODEL_PATH):
        emotion_model = load_model(Config.MODEL_PATH, compile=False)
        MODEL_LOADED = True
        print("[INFO] pre-trained mini_XCEPTION model loaded successfully.")
    else:
        print(f"[WARNING] pre-trained model file not found at: {Config.MODEL_PATH}. Running in Simulation Mode.")
except Exception as e:
    print(f"[ERROR] Failed to load TensorFlow/Keras model: {e}. Running in Simulation Mode.")

# Load Haar Cascade
face_cascade = cv2.CascadeClassifier(Config.HAAR_CASCADE_PATH)
if face_cascade.empty():
    print(f"[ERROR] Failed to load face Haar Cascade from: {Config.HAAR_CASCADE_PATH}")

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# MongoDB Integration
import pymongo
client = None
db = None
try:
    client = pymongo.MongoClient(app.config['MONGO_URI'], serverSelectionTimeoutMS=5000)
    # Check connection
    client.server_info()
    try:
        db = client.get_database()
    except Exception:
        db = client['emotion_music_db']
    print("[INFO] Connected to MongoDB Atlas/Local successfully.")
except Exception as e:
    print(f"[CRITICAL] Failed to connect to MongoDB: {e}")
    sys.exit(1)

# Emotion Labels
EMOTIONS = ["angry", "disgust", "scared", "happy", "sad", "surprised", "neutral"]

# Decorators for authentication
def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for('login'))
        # Check if user is suspended
        user = db.users.find_one({"_id": ObjectId(session['user_id'])})
        if not user or user.get('status', 'active') == 'suspended':
            session.clear()
            flash("Your account has been suspended. Please contact support.", "error")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash("You do not have administrator permissions to access this page.", "error")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# Populate defaults (Default Admin and default songs)
def seed_database():
    # 1. Admin account seeding
    admin_exists = db.users.find_one({"role": "admin"})
    if not admin_exists:
        admin_pwd_hash = generate_password_hash("admin123")
        db.users.insert_one({
            "name": "System Admin",
            "username": "admin",
            "email": "admin@emosic.com",
            "password_hash": admin_pwd_hash,
            "role": "admin",
            "profile_picture": "default_avatar.png",
            "status": "active",
            "created_at": datetime.datetime.utcnow(),
            "last_login": None
        })
        print("[DATABASE SEED] Default Admin account created: admin@emosic.com / admin123")

    # 2. Songs seeding
    songs_count = db.songs.count_documents({})
    if songs_count == 0:
        default_songs = [
            {"emotion": "happy", "title": "Summer Bliss", "artist": "Lumina Beats", "audio_url": "/static/songs/happy_default.mp3", "cover_image": "/static/covers/happy_default.png"},
            {"emotion": "happy", "title": "Sunny Skies", "artist": "The Horizons", "audio_url": "/static/songs/happy_sky.mp3", "cover_image": "/static/covers/happy_sky.png"},
            {"emotion": "sad", "title": "Rainy Windowpane", "artist": "Acoustic Whispers", "audio_url": "/static/songs/sad_default.mp3", "cover_image": "/static/covers/sad_default.png"},
            {"emotion": "sad", "title": "Lost Memory", "artist": "Ethereal Echoes", "audio_url": "/static/songs/sad_lost.mp3", "cover_image": "/static/covers/sad_lost.png"},
            {"emotion": "angry", "title": "Rage Protocol", "artist": "Cyber Shock", "audio_url": "/static/songs/angry_default.mp3", "cover_image": "/static/covers/angry_default.png"},
            {"emotion": "disgust", "title": "Grimy Alleyway", "artist": "Subterranean Collective", "audio_url": "/static/songs/disgust_default.mp3", "cover_image": "/static/covers/disgust_default.png"},
            {"emotion": "scared", "title": "Midnight Fear", "artist": "Spectral Drift", "audio_url": "/static/songs/scared_default.mp3", "cover_image": "/static/covers/scared_default.png"},
            {"emotion": "surprised", "title": "Awe and Wonder", "artist": "Nebula", "audio_url": "/static/songs/surprised_default.mp3", "cover_image": "/static/covers/surprised_default.png"},
            {"emotion": "neutral", "title": "Calm Reflection", "artist": "Lo-Fi Focus", "audio_url": "/static/songs/neutral_default.mp3", "cover_image": "/static/covers/neutral_default.png"},
            {"emotion": "neutral", "title": "Steady Stream", "artist": "Zen Ambient", "audio_url": "/static/songs/neutral_stream.mp3", "cover_image": "/static/covers/neutral_stream.png"}
        ]
        db.songs.insert_many(default_songs)
        
        # Write tiny dummy assets if not exist
        os.makedirs("static/songs", exist_ok=True)
        os.makedirs("static/covers", exist_ok=True)
        
        tiny_png = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
        tiny_mp3 = b'\xff\xfb\x90\x44\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        
        for song in default_songs:
            audio_path = song["audio_url"].lstrip('/')
            cover_path = song["cover_image"].lstrip('/')
            if not os.path.exists(audio_path):
                with open(audio_path, 'wb') as f:
                    f.write(tiny_mp3)
            if not os.path.exists(cover_path):
                with open(cover_path, 'wb') as f:
                    f.write(tiny_png)
                    
        print("[DATABASE SEED] Seeded default songs and dummy media assets successfully.")

seed_database()

# Helpers
def validate_email(email):
    return re.match(r'[^@]+@[^@]+\.[^@]+', email) is not None

def validate_password_strength(password):
    # Min 8 chars, 1 uppercase, 1 lowercase, 1 number, 1 special char
    if len(password) < 8:
        return False, "Password must be at least 8 characters long."
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter."
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter."
    if not re.search(r"\d", password):
        return False, "Password must contain at least one digit."
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character."
    return True, ""

# ----------------- ROUTING -----------------

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('landing.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        if not name or not username or not email or not password:
            flash("All fields are required.", "error")
            return render_template('register.html')
            
        if not validate_email(email):
            flash("Invalid email format.", "error")
            return render_template('register.html')
            
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template('register.html')
            
        is_strong, pwd_err = validate_password_strength(password)
        if not is_strong:
            flash(pwd_err, "error")
            return render_template('register.html')
            
        # Check duplicate username or email
        existing_user = db.users.find_one({"$or": [{"email": email}, {"username": username}]})
        if existing_user:
            if existing_user['email'] == email:
                flash("Email is already registered.", "error")
            else:
                flash("Username is already taken.", "error")
            return render_template('register.html')
            
        # Create user
        password_hash = generate_password_hash(password)
        new_user = {
            "name": name,
            "username": username,
            "email": email,
            "password_hash": password_hash,
            "role": "user",
            "profile_picture": "default_avatar.png",
            "status": "active",
            "created_at": datetime.datetime.utcnow(),
            "last_login": None
        }
        db.users.insert_one(new_user)
        flash("Registration successful! Please login.", "success")
        return redirect(url_for('login'))
        
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        login_credential = request.form.get('email_username', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember')
        
        if not login_credential or not password:
            flash("Username/Email and password are required.", "error")
            return render_template('login.html')
            
        # Find user
        user = db.users.find_one({"$or": [{"email": login_credential}, {"username": login_credential}]})
        
        if not user or not check_password_hash(user['password_hash'], password):
            flash("Invalid email/username or password.", "error")
            return render_template('login.html')
            
        if user.get('status', 'active') == 'suspended':
            flash("Your account has been suspended.", "error")
            return render_template('login.html')
            
        # Set session
        session.clear()
        session['user_id'] = str(user['_id'])
        session['username'] = user['username']
        session['email'] = user['email']
        session['role'] = user.get('role', 'user')
        
        # Configure session timeout
        if remember:
            session.permanent = True
            app.permanent_session_lifetime = datetime.timedelta(days=30)
        else:
            session.permanent = False
            
        # Update last login
        db.users.update_one({"_id": user['_id']}, {"$set": {"last_login": datetime.datetime.utcnow()}})
        
        flash(f"Welcome back, {user['name']}!", "success")
        if user.get('role') == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))
        
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been successfully logged out.", "success")
    return redirect(url_for('login'))

def send_otp_email(to_email, otp):
    body_text = f"""Hello,

You requested a password reset code for your EmoSic account.

Your verification OTP code is:
{otp}

This code will expire in 5 minutes. If you did not request this, please ignore this email.

Best regards,
The EmoSic Team
"""

    # Method 1: Resend HTTP API (Recommended for production, since ports 587/465 are often blocked by clouds)
    if Config.RESEND_API_KEY:
        import urllib.request
        import json
        try:
            url = "https://api.resend.com/emails"
            headers = {
                "Authorization": f"Bearer {Config.RESEND_API_KEY}",
                "Content-Type": "application/json"
            }
            # For Resend, default sender must match a verified domain or onboarding@resend.dev
            sender = Config.MAIL_DEFAULT_SENDER if '@' in Config.MAIL_DEFAULT_SENDER and 'no-reply@emosic.com' not in Config.MAIL_DEFAULT_SENDER else 'onboarding@resend.dev'
            
            data = {
                "from": f"EmoSic <{sender}>",
                "to": [to_email],
                "subject": "EmoSic - Password Reset OTP",
                "text": body_text
            }
            req = urllib.request.Request(
                url, 
                data=json.dumps(data).encode('utf-8'), 
                headers=headers, 
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                resp_code = response.getcode()
                if resp_code in [200, 201, 202]:
                    print(f"[MAIL SUCCESS] Password reset OTP sent to {to_email} via Resend HTTP API")
                    return True
                else:
                    print(f"[MAIL ERROR] Resend API returned status code: {resp_code}")
                    return False
        except Exception as e:
            print(f"[MAIL ERROR] Failed to send email via Resend API: {e}")
            # Fall back to SMTP if it is configured
            if not Config.MAIL_SERVER:
                return False

    # Method 2: Standard SMTP Fallback
    if not all([Config.MAIL_SERVER, Config.MAIL_USERNAME, Config.MAIL_PASSWORD]):
        print(f"[MAIL WARNING] Mail server credentials are not fully configured in environment variables. Falling back to console logging.")
        return False

    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    try:
        msg = MIMEMultipart()
        msg['From'] = Config.MAIL_DEFAULT_SENDER
        msg['To'] = to_email
        msg['Subject'] = "EmoSic - Password Reset OTP"
        msg.attach(MIMEText(body_text, 'plain'))

        # Connect to SMTP server
        server = smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=10)
        if Config.MAIL_USE_TLS:
            server.starttls()
        
        server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
        server.send_message(msg)
        server.close()
        print(f"[MAIL SUCCESS] Password reset OTP sent to {to_email} via SMTP")
        return True
    except Exception as e:
        print(f"[MAIL ERROR] Failed to send email to {to_email} via SMTP: {e}")
        return False

@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'request_otp':
            email = request.form.get('email', '').strip().lower()
            user = db.users.find_one({"email": email})
            if not user:
                flash("Email not registered.", "error")
                return render_template('forgot_password.html')
                
            # Generate OTP
            otp = str(random.randint(100000, 999999))
            session['reset_otp'] = otp
            session['reset_email'] = email
            session['otp_expiry'] = (datetime.datetime.utcnow() + datetime.timedelta(minutes=5)).timestamp()
            
            # Print to console for developer testing
            print("==========================================")
            print(f"[OTP REQUEST] Password reset requested for: {email}")
            print(f"[OTP CODE] Verification OTP: {otp}")
            print("==========================================")
            
            # Attempt to send email
            mail_sent = send_otp_email(email, otp)
            if mail_sent:
                flash("An OTP verification code has been sent to your email. Enter it below.", "success")
            else:
                flash("An OTP verification code has been printed to the system server logs/console. Enter it below.", "info")
                
            return render_template('forgot_password.html', step='verify_otp')
            
        elif action == 'verify_otp':
            entered_otp = request.form.get('otp', '').strip()
            session_otp = session.get('reset_otp')
            otp_expiry = session.get('otp_expiry', 0)
            
            if not session_otp or datetime.datetime.utcnow().timestamp() > otp_expiry:
                flash("OTP has expired or is invalid. Please request a new one.", "error")
                return redirect(url_for('forgot_password'))
                
            if entered_otp != session_otp:
                flash("Incorrect OTP code. Try again.", "error")
                return render_template('forgot_password.html', step='verify_otp')
                
            # Valid OTP, proceed to new password creation
            session['otp_verified'] = True
            return render_template('forgot_password.html', step='reset_password')
            
        elif action == 'reset_password':
            if not session.get('otp_verified'):
                flash("Unauthorized access. Please start the verification process again.", "error")
                return redirect(url_for('forgot_password'))
                
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            email = session.get('reset_email')
            
            if password != confirm_password:
                flash("Passwords do not match.", "error")
                return render_template('forgot_password.html', step='reset_password')
                
            is_strong, pwd_err = validate_password_strength(password)
            if not is_strong:
                flash(pwd_err, "error")
                return render_template('forgot_password.html', step='reset_password')
                
            # Update password
            pwd_hash = generate_password_hash(password)
            db.users.update_one({"email": email}, {"$set": {"password_hash": pwd_hash}})
            
            # Clear reset session items
            session.pop('reset_otp', None)
            session.pop('reset_email', None)
            session.pop('otp_expiry', None)
            session.pop('otp_verified', None)
            
            flash("Your password has been successfully reset! You can now log in.", "success")
            return redirect(url_for('login'))
            
    return render_template('forgot_password.html', step='request_email')

@app.route('/dashboard')
@login_required
def dashboard():
    user = db.users.find_one({"_id": ObjectId(session['user_id'])})
    
    # Dashboard metrics
    total_scans = db.emotions.count_documents({"user_id": ObjectId(session['user_id'])})
    favorite_songs_count = db.favorites.count_documents({"user_id": ObjectId(session['user_id'])})
    
    # Calculate favorite emotion
    pipeline = [
        {"$match": {"user_id": ObjectId(session['user_id'])}},
        {"$group": {"_id": "$emotion", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 1}
    ]
    fav_emotion_cursor = list(db.emotions.aggregate(pipeline))
    favorite_emotion = fav_emotion_cursor[0]['_id'].capitalize() if fav_emotion_cursor else "N/A"
    
    # Profile pic
    pfp = user.get('profile_picture', 'default_avatar.png')
    
    return render_template('dashboard.html', 
                           user=user, 
                           total_scans=total_scans,
                           favorite_emotion=favorite_emotion,
                           favorite_songs_count=favorite_songs_count,
                           profile_picture=pfp)

@app.route('/profile')
@login_required
def profile():
    user = db.users.find_one({"_id": ObjectId(session['user_id'])})
    pfp = user.get('profile_picture', 'default_avatar.png')
    return render_template('profile.html', user=user, profile_picture=pfp)

@app.route('/profile/update', methods=['POST'])
@login_required
def profile_update():
    name = request.form.get('name', '').strip()
    email = request.form.get('email', '').strip().lower()
    
    if not name or not email:
        flash("Name and email are required.", "error")
        return redirect(url_for('profile'))
        
    if not validate_email(email):
        flash("Invalid email format.", "error")
        return redirect(url_for('profile'))
        
    # Check duplicate email
    duplicate = db.users.find_one({"email": email, "_id": {"$ne": ObjectId(session['user_id'])}})
    if duplicate:
        flash("Email is already in use by another user.", "error")
        return redirect(url_for('profile'))
        
    db.users.update_one(
        {"_id": ObjectId(session['user_id'])},
        {"$set": {"name": name, "email": email}}
    )
    session['email'] = email
    flash("Profile updated successfully.", "success")
    return redirect(url_for('profile'))

@app.route('/profile/change_password', methods=['POST'])
@login_required
def profile_change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    user = db.users.find_one({"_id": ObjectId(session['user_id'])})
    
    if not check_password_hash(user['password_hash'], current_password):
        flash("Current password is incorrect.", "error")
        return redirect(url_for('profile'))
        
    if new_password != confirm_password:
        flash("Passwords do not match.", "error")
        return redirect(url_for('profile'))
        
    is_strong, pwd_err = validate_password_strength(new_password)
    if not is_strong:
        flash(pwd_err, "error")
        return redirect(url_for('profile'))
        
    db.users.update_one(
        {"_id": ObjectId(session['user_id'])},
        {"$set": {"password_hash": generate_password_hash(new_password)}}
    )
    flash("Password updated successfully.", "success")
    return redirect(url_for('profile'))

@app.route('/profile/avatar', methods=['POST'])
@login_required
def profile_avatar():
    if 'avatar' not in request.files:
        flash("No file part.", "error")
        return redirect(url_for('profile'))
        
    file = request.files['avatar']
    if file.filename == '':
        flash("No file selected.", "error")
        return redirect(url_for('profile'))
        
    if file and app.config.allowed_file(file.filename, app.config['ALLOWED_IMAGE_EXTENSIONS']):
        filename = secure_filename(f"avatar_{session['user_id']}_{file.filename}")
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Save relative URL or path
        db.users.update_one(
            {"_id": ObjectId(session['user_id'])},
            {"$set": {"profile_picture": filename}}
        )
        flash("Profile picture updated.", "success")
    else:
        flash("Allowed file types: png, jpg, jpeg, gif", "error")
        
    return redirect(url_for('profile'))

@app.route('/profile/delete', methods=['POST'])
@login_required
def profile_delete():
    user_id = ObjectId(session['user_id'])
    
    # Remove files
    user_detections = db.emotions.find({"user_id": user_id})
    for d in user_detections:
        img_path = d.get('image_path', '')
        if img_path.startswith('/static/uploads/'):
            filename = img_path.replace('/static/uploads/', '')
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            except:
                pass
                
    # Remove database entries
    db.emotions.delete_many({"user_id": user_id})
    db.favorites.delete_many({"user_id": user_id})
    db.users.delete_one({"_id": user_id})
    
    session.clear()
    flash("Your account has been deleted successfully.", "success")
    return redirect(url_for('index'))

@app.route('/profile/export')
@login_required
def profile_export():
    user_id = ObjectId(session['user_id'])
    user = db.users.find_one({"_id": user_id})
    detections = list(db.emotions.find({"user_id": user_id}))
    favorites = list(db.favorites.find({"user_id": user_id}))
    
    # Format bson items for json
    user_clean = {
        "name": user["name"],
        "username": user["username"],
        "email": user["email"],
        "role": user.get("role", "user"),
        "created_at": user["created_at"].isoformat() if user.get("created_at") else None
    }
    
    detections_clean = []
    for d in detections:
        detections_clean.append({
            "emotion": d["emotion"],
            "confidence": d["confidence"],
            "timestamp": d["timestamp"].isoformat() if d.get("timestamp") else None
        })
        
    favorites_clean = []
    for f in favorites:
        song = db.songs.find_one({"_id": ObjectId(f["song_id"])})
        if song:
            favorites_clean.append({
                "title": song["title"],
                "artist": song["artist"],
                "emotion": song["emotion"],
                "added_at": f["created_at"].isoformat() if f.get("created_at") else None
            })
            
    export_data = {
        "user": user_clean,
        "history": detections_clean,
        "favorites": favorites_clean
    }
    
    response = jsonify(export_data)
    response.headers.set("Content-Disposition", "attachment", filename=f"emosic_personal_data_{session['username']}.json")
    return response

@app.route('/emotion')
@login_required
def emotion_page():
    return render_template('emotion.html')

@app.route('/detect', methods=['POST'])
@login_required
def detect():
    data = request.get_json()
    if not data or 'image' not in data:
        return jsonify({"success": False, "error": "No image sent"}), 400
        
    try:
        # Parse base64
        header, encoded = data['image'].split(",", 1)
        img_bytes = base64.b64decode(encoded)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            return jsonify({"success": False, "error": "Could not parse image"}), 400
            
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Face detect
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
        
        if len(faces) == 0:
            return jsonify({"success": True, "face_detected": False})
            
        # Largest face
        faces = sorted(faces, key=lambda f: f[2]*f[3], reverse=True)
        (x, y, w, h) = faces[0]
        
        roi_gray = gray[y:y+h, x:x+w]
        
        # Predict emotion
        probabilities = {}
        predicted_emotion = "neutral"
        confidence = 0.5
        
        if MODEL_LOADED:
            roi_gray = cv2.resize(roi_gray, (64, 64))
            roi_gray = roi_gray.astype("float32") / 255.0
            roi_gray = (roi_gray - 0.5) * 2.0
            roi_gray = np.expand_dims(roi_gray, axis=0)
            roi_gray = np.expand_dims(roi_gray, axis=-1)
            
            preds = emotion_model.predict(roi_gray)[0]
            emotion_idx = np.argmax(preds)
            predicted_emotion = EMOTIONS[emotion_idx]
            confidence = float(preds[emotion_idx])
            probabilities = {EMOTIONS[i]: float(preds[i]) for i in range(len(EMOTIONS))}
        else:
            # Simulation Mode Fallback
            predicted_emotion = random.choice(EMOTIONS)
            confidence = random.uniform(0.65, 0.95)
            raw_probs = [random.random() for _ in EMOTIONS]
            sum_probs = sum(raw_probs)
            probabilities = {EMOTIONS[i]: raw_probs[i]/sum_probs for i in range(len(EMOTIONS))}
            probabilities[predicted_emotion] = confidence
            remaining = 1.0 - confidence
            other_sum = sum(probabilities[e] for e in EMOTIONS if e != predicted_emotion)
            for e in EMOTIONS:
                if e != predicted_emotion:
                    probabilities[e] = (probabilities[e]/other_sum) * remaining
                    
        # Save crop
        filename = f"crop_{session['user_id']}_{int(datetime.datetime.utcnow().timestamp())}.jpg"
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        cv2.imwrite(filepath, img[y:y+h, x:x+w])
        image_path = f"/static/uploads/{filename}"
        
        # Save to database
        db.emotions.insert_one({
            "user_id": ObjectId(session['user_id']),
            "emotion": predicted_emotion,
            "confidence": confidence,
            "timestamp": datetime.datetime.utcnow(),
            "image_path": image_path
        })
        
        # Load recommendations
        recommended = list(db.songs.find({"emotion": predicted_emotion}))
        
        # Get list of favorites
        favorites = list(db.favorites.find({"user_id": ObjectId(session['user_id'])}))
        favorite_song_ids = {str(fav["song_id"]) for fav in favorites}
        
        songs_list = []
        for song in recommended:
            songs_list.append({
                "id": str(song["_id"]),
                "title": song["title"],
                "artist": song["artist"],
                "audio_url": song["audio_url"],
                "cover_image": song["cover_image"],
                "is_favorite": str(song["_id"]) in favorite_song_ids
            })
            
        return jsonify({
            "success": True,
            "face_detected": True,
            "emotion": predicted_emotion,
            "confidence": confidence,
            "probabilities": probabilities,
            "box": [int(x), int(y), int(w), int(h)],
            "songs": songs_list
        })
        
    except Exception as e:
        print(f"[ERROR] Detection failed: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/history')
@login_required
def history():
    user_id = ObjectId(session['user_id'])
    
    # Filters
    time_filter = request.args.get('filter', 'all')
    now = datetime.datetime.utcnow()
    query = {"user_id": user_id}
    
    if time_filter == 'today':
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        query["timestamp"] = {"$gte": start}
    elif time_filter == 'week':
        start = now - datetime.timedelta(days=7)
        query["timestamp"] = {"$gte": start}
    elif time_filter == 'month':
        start = now - datetime.timedelta(days=30)
        query["timestamp"] = {"$gte": start}
    elif time_filter == 'custom':
        start_str = request.args.get('start_date')
        end_str = request.args.get('end_date')
        if start_str and end_str:
            try:
                start = datetime.datetime.strptime(start_str, "%Y-%m-%d")
                end = datetime.datetime.strptime(end_str, "%Y-%m-%d") + datetime.timedelta(days=1)
                query["timestamp"] = {"$gte": start, "$lte": end}
            except ValueError:
                pass
                
    detections = list(db.emotions.find(query).sort("timestamp", -1))
    return render_template('history.html', detections=detections, active_filter=time_filter)

@app.route('/history/delete/<detection_id>', methods=['POST'])
@login_required
def delete_detection(detection_id):
    query = {"_id": ObjectId(detection_id)}
    # Standard user can only delete their own history
    if session.get('role') != 'admin':
        query["user_id"] = ObjectId(session['user_id'])
        
    record = db.emotions.find_one(query)
    if record:
        img_path = record.get('image_path', '')
        if img_path.startswith('/static/uploads/'):
            filename = img_path.replace('/static/uploads/', '')
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            except:
                pass
        db.emotions.delete_one({"_id": record["_id"]})
        flash("Record deleted successfully.", "success")
    else:
        flash("Record not found.", "error")
        
    return redirect(request.referrer or url_for('history'))

@app.route('/history/export/<export_format>')
@login_required
def export_history(export_format):
    user_id = ObjectId(session['user_id'])
    detections = list(db.emotions.find({"user_id": user_id}).sort("timestamp", -1))
    
    if export_format == 'csv':
        import csv
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Timestamp", "Emotion", "Confidence", "Image Path"])
        
        for d in detections:
            writer.writerow([
                d["timestamp"].strftime("%Y-%m-%d %H:%M:%S") if d.get("timestamp") else "",
                d["emotion"],
                f"{d['confidence']*100:.2f}%",
                d.get("image_path", "")
            ])
            
        response = make_response(output.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename=emosic_history_{session['username']}.csv"
        response.headers["Content-type"] = "text/csv"
        return response
        
    elif export_format == 'pdf':
        # Render clean template for printing
        return render_template('history_print.html', detections=detections, datetime=datetime.datetime)
        
    flash("Invalid export format requested.", "error")
    return redirect(url_for('history'))

# Helper for CSV output response
from flask import make_response

@app.route('/analytics')
@login_required
def analytics():
    user_id = ObjectId(session['user_id'])
    detections = list(db.emotions.find({"user_id": user_id}))
    
    # Emotion distribution counts
    emotion_counts = {e: 0 for e in EMOTIONS}
    for d in detections:
        emotion_counts[d['emotion']] = emotion_counts.get(d['emotion'], 0) + 1
        
    # Weekly emotion counts (last 7 days)
    now = datetime.datetime.utcnow()
    weekly_trends = []
    labels = []
    
    for i in range(6, -1, -1):
        day = now - datetime.timedelta(days=i)
        start_day = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end_day = day.replace(hour=23, minute=59, second=59, microsecond=999)
        day_label = day.strftime("%a")
        labels.append(day_label)
        
        day_scans = db.emotions.count_documents({
            "user_id": user_id,
            "timestamp": {"$gte": start_day, "$lte": end_day}
        })
        weekly_trends.append(day_scans)
        
    # Analytics parameters to inject into chart.js
    most_common = max(emotion_counts, key=emotion_counts.get) if detections else "N/A"
    most_common_count = emotion_counts[most_common] if detections else 0
    
    return render_template('analytics.html',
                           labels=labels,
                           weekly_trends=weekly_trends,
                           emotion_counts=emotion_counts,
                           most_common=most_common.capitalize(),
                           most_common_count=most_common_count,
                           total_scans=len(detections))

@app.route('/favorites/add/<song_id>', methods=['POST'])
@login_required
def add_favorite(song_id):
    user_id = ObjectId(session['user_id'])
    song_oid = ObjectId(song_id)
    
    # Check if exists
    existing = db.favorites.find_one({"user_id": user_id, "song_id": song_oid})
    if not existing:
        db.favorites.insert_one({
            "user_id": user_id,
            "song_id": song_oid,
            "created_at": datetime.datetime.utcnow()
        })
        return jsonify({"success": True, "message": "Song added to favorites!"})
    return jsonify({"success": False, "message": "Already favorited."})

@app.route('/favorites/remove/<song_id>', methods=['POST'])
@login_required
def remove_favorite(song_id):
    user_id = ObjectId(session['user_id'])
    song_oid = ObjectId(song_id)
    
    db.favorites.delete_one({"user_id": user_id, "song_id": song_oid})
    return jsonify({"success": True, "message": "Song removed from favorites."})

# ----------------- ADMIN PORTAL -----------------

@app.route('/admin/debug-mail')
@login_required
@admin_required
def debug_mail():
    config_status = {
        "MAIL_SERVER": Config.MAIL_SERVER,
        "MAIL_PORT": Config.MAIL_PORT,
        "MAIL_USE_TLS": Config.MAIL_USE_TLS,
        "MAIL_USERNAME": Config.MAIL_USERNAME,
        "MAIL_PASSWORD_SET": bool(Config.MAIL_PASSWORD),
        "MAIL_DEFAULT_SENDER": Config.MAIL_DEFAULT_SENDER,
        "RESEND_API_KEY_SET": bool(Config.RESEND_API_KEY)
    }
    
    smtp_test_result = "Not run"
    if Config.MAIL_SERVER and Config.MAIL_USERNAME and Config.MAIL_PASSWORD:
        import smtplib
        try:
            server = smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=5)
            if Config.MAIL_USE_TLS:
                server.starttls()
            server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            server.close()
            smtp_test_result = "Success: Successfully connected and authenticated with SMTP server."
        except Exception as e:
            smtp_test_result = f"Failed: {e}"
    else:
        smtp_test_result = "Skipped: Missing server, username, or password credentials."

    resend_test_result = "Not run"
    if Config.RESEND_API_KEY:
        import urllib.request
        import urllib.error
        try:
            url = "https://api.resend.com/emails"
            req = urllib.request.Request(url, method='POST')
            try:
                urllib.request.urlopen(req, timeout=5)
            except urllib.error.HTTPError as he:
                if he.code in [400, 401, 422]:
                    resend_test_result = f"Success: Connected successfully to Resend API. (HTTP Status {he.code})"
                else:
                    resend_test_result = f"Failed: Resend API returned error {he.code}: {he.reason}"
            except Exception as ex:
                resend_test_result = f"Failed: {ex}"
        except Exception as e:
            resend_test_result = f"Failed: {e}"
    else:
        resend_test_result = "Skipped: Missing Resend API key."

    return jsonify({
        "config": config_status,
        "smtp_connection_test": smtp_test_result,
        "resend_connection_test": resend_test_result
    })

@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    total_users = db.users.count_documents({})
    total_songs = db.songs.count_documents({})
    total_detections = db.emotions.count_documents({})
    active_users = db.users.count_documents({"status": "active"})
    
    # Calculate global most detected emotion
    pipeline = [
        {"$group": {"_id": "$emotion", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": 1}
    ]
    fav_emotion_cursor = list(db.emotions.aggregate(pipeline))
    most_detected = fav_emotion_cursor[0]['_id'].capitalize() if fav_emotion_cursor else "N/A"
    
    # Calculate user registration trend (past 5 months)
    # Simple groupings
    user_growth = []
    growth_labels = []
    now = datetime.datetime.utcnow()
    
    for i in range(4, -1, -1):
        # Calculate month offsets
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        label = datetime.date(year, month, 1).strftime("%b %Y")
        growth_labels.append(label)
        
        # Calculate counts up to end of this month
        if month == 12:
            end_date = datetime.datetime(year + 1, 1, 1)
        else:
            end_date = datetime.datetime(year, month + 1, 1)
            
        count = db.users.count_documents({"created_at": {"$lt": end_date}})
        user_growth.append(count)
        
    return render_template('admin/dashboard.html',
                           total_users=total_users,
                           total_songs=total_songs,
                           total_detections=total_detections,
                           active_users=active_users,
                           most_detected=most_detected,
                           growth_labels=growth_labels,
                           user_growth=user_growth)

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    search_query = request.args.get('search', '').strip()
    query = {}
    if search_query:
        query = {"$or": [
            {"name": {"$regex": search_query, "$options": "i"}},
            {"username": {"$regex": search_query, "$options": "i"}},
            {"email": {"$regex": search_query, "$options": "i"}}
        ]}
    users = list(db.users.find(query).sort("created_at", -1))
    return render_template('admin/users.html', users=users, search_query=search_query)

@app.route('/admin/users/toggle_status/<user_id>', methods=['POST'])
@login_required
@admin_required
def admin_toggle_status(user_id):
    # Cannot suspend oneself
    if user_id == session['user_id']:
        flash("You cannot suspend your own account.", "error")
        return redirect(url_for('admin_users'))
        
    user = db.users.find_one({"_id": ObjectId(user_id)})
    if user:
        new_status = 'suspended' if user.get('status', 'active') == 'active' else 'active'
        db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"status": new_status}})
        flash(f"User status updated to {new_status}.", "success")
    else:
        flash("User not found.", "error")
    return redirect(url_for('admin_users'))

@app.route('/admin/users/edit/<user_id>', methods=['POST'])
@login_required
@admin_required
def admin_edit_user(user_id):
    name = request.form.get('name', '').strip()
    role = request.form.get('role', 'user')
    status = request.form.get('status', 'active')
    
    if not name:
        flash("Name cannot be empty.", "error")
        return redirect(url_for('admin_users'))
        
    db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"name": name, "role": role, "status": status}}
    )
    flash("User details updated.", "success")
    return redirect(url_for('admin_users'))

@app.route('/admin/users/delete/<user_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_user(user_id):
    if user_id == session['user_id']:
        flash("You cannot delete your own admin account.", "error")
        return redirect(url_for('admin_users'))
        
    user_oid = ObjectId(user_id)
    # Remove files
    detections = db.emotions.find({"user_id": user_oid})
    for d in detections:
        img_path = d.get('image_path', '')
        if img_path.startswith('/static/uploads/'):
            filename = img_path.replace('/static/uploads/', '')
            try:
                os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            except:
                pass
                
    db.emotions.delete_many({"user_id": user_oid})
    db.favorites.delete_many({"user_id": user_oid})
    db.users.delete_one({"_id": user_oid})
    
    flash("User account and database records deleted successfully.", "success")
    return redirect(url_for('admin_users'))

@app.route('/admin/songs')
@login_required
@admin_required
def admin_songs():
    songs = list(db.songs.find({}).sort("emotion", 1))
    return render_template('admin/songs.html', songs=songs, emotions=EMOTIONS)

@app.route('/admin/songs/add', methods=['POST'])
@login_required
@admin_required
def admin_add_song():
    title = request.form.get('title', '').strip()
    artist = request.form.get('artist', '').strip()
    emotion = request.form.get('emotion', '').lower()
    
    if not title or not artist or not emotion:
        flash("All text fields are required.", "error")
        return redirect(url_for('admin_songs'))
        
    if 'audio' not in request.files or 'cover' not in request.files:
        flash("Audio and Cover files are required.", "error")
        return redirect(url_for('admin_songs'))
        
    audio_file = request.files['audio']
    cover_file = request.files['cover']
    
    if audio_file.filename == '' or cover_file.filename == '':
        flash("Please upload both audio and cover image files.", "error")
        return redirect(url_for('admin_songs'))
        
    if not app.config.allowed_file(audio_file.filename, app.config['ALLOWED_AUDIO_EXTENSIONS']):
        flash("Audio must be mp3, wav, or ogg format.", "error")
        return redirect(url_for('admin_songs'))
        
    if not app.config.allowed_file(cover_file.filename, app.config['ALLOWED_IMAGE_EXTENSIONS']):
        flash("Cover must be png, jpg, jpeg, or gif format.", "error")
        return redirect(url_for('admin_songs'))
        
    os.makedirs(app.config['SONG_FOLDER'], exist_ok=True)
    os.makedirs(app.config['COVER_FOLDER'], exist_ok=True)
    
    audio_filename = secure_filename(f"{int(datetime.datetime.utcnow().timestamp())}_{audio_file.filename}")
    cover_filename = secure_filename(f"{int(datetime.datetime.utcnow().timestamp())}_{cover_file.filename}")
    
    audio_file.save(os.path.join(app.config['SONG_FOLDER'], audio_filename))
    cover_file.save(os.path.join(app.config['COVER_FOLDER'], cover_filename))
    
    db.songs.insert_one({
        "emotion": emotion,
        "title": title,
        "artist": artist,
        "audio_url": f"/static/songs/{audio_filename}",
        "cover_image": f"/static/covers/{cover_filename}"
    })
    
    flash("Song added successfully.", "success")
    return redirect(url_for('admin_songs'))

@app.route('/admin/songs/edit/<song_id>', methods=['POST'])
@login_required
@admin_required
def admin_edit_song(song_id):
    title = request.form.get('title', '').strip()
    artist = request.form.get('artist', '').strip()
    emotion = request.form.get('emotion', '').lower()
    
    if not title or not artist or not emotion:
        flash("Text fields cannot be empty.", "error")
        return redirect(url_for('admin_songs'))
        
    song_oid = ObjectId(song_id)
    song = db.songs.find_one({"_id": song_oid})
    
    if not song:
        flash("Song not found.", "error")
        return redirect(url_for('admin_songs'))
        
    update_data = {
        "title": title,
        "artist": artist,
        "emotion": emotion
    }
    
    # Optional audio replacement
    if 'audio' in request.files and request.files['audio'].filename != '':
        audio_file = request.files['audio']
        if app.config.allowed_file(audio_file.filename, app.config['ALLOWED_AUDIO_EXTENSIONS']):
            # Remove old file
            old_audio = song.get('audio_url', '')
            if old_audio.startswith('/static/songs/'):
                try:
                    os.remove(os.path.join(app.config['SONG_FOLDER'], old_audio.replace('/static/songs/', '')))
                except:
                    pass
            # Save new
            audio_filename = secure_filename(f"{int(datetime.datetime.utcnow().timestamp())}_{audio_file.filename}")
            audio_file.save(os.path.join(app.config['SONG_FOLDER'], audio_filename))
            update_data["audio_url"] = f"/static/songs/{audio_filename}"
            
    # Optional cover replacement
    if 'cover' in request.files and request.files['cover'].filename != '':
        cover_file = request.files['cover']
        if app.config.allowed_file(cover_file.filename, app.config['ALLOWED_IMAGE_EXTENSIONS']):
            # Remove old file
            old_cover = song.get('cover_image', '')
            if old_cover.startswith('/static/covers/'):
                try:
                    os.remove(os.path.join(app.config['COVER_FOLDER'], old_cover.replace('/static/covers/', '')))
                except:
                    pass
            # Save new
            cover_filename = secure_filename(f"{int(datetime.datetime.utcnow().timestamp())}_{cover_file.filename}")
            cover_file.save(os.path.join(app.config['COVER_FOLDER'], cover_filename))
            update_data["cover_image"] = f"/static/covers/{cover_filename}"
            
    db.songs.update_one({"_id": song_oid}, {"$set": update_data})
    flash("Song updated successfully.", "success")
    return redirect(url_for('admin_songs'))

@app.route('/admin/songs/delete/<song_id>', methods=['POST'])
@login_required
@admin_required
def admin_delete_song(song_id):
    song_oid = ObjectId(song_id)
    song = db.songs.find_one({"_id": song_oid})
    
    if song:
        # Delete audio file
        audio_url = song.get('audio_url', '')
        if audio_url.startswith('/static/songs/'):
            filename = audio_url.replace('/static/songs/', '')
            try:
                os.remove(os.path.join(app.config['SONG_FOLDER'], filename))
            except:
                pass
                
        # Delete cover file
        cover_image = song.get('cover_image', '')
        if cover_image.startswith('/static/covers/'):
            filename = cover_image.replace('/static/covers/', '')
            try:
                os.remove(os.path.join(app.config['COVER_FOLDER'], filename))
            except:
                pass
                
        # Delete DB entries (song and associated favorites references)
        db.songs.delete_one({"_id": song_oid})
        db.favorites.delete_many({"song_id": song_oid})
        flash("Song deleted successfully.", "success")
    else:
        flash("Song not found.", "error")
        
    return redirect(url_for('admin_songs'))

@app.route('/admin/detections')
@login_required
@admin_required
def admin_detections():
    # Filter by user or emotion
    user_filter = request.args.get('user', '').strip()
    emotion_filter = request.args.get('emotion', '').strip().lower()
    
    query = {}
    if emotion_filter and emotion_filter in EMOTIONS:
        query["emotion"] = emotion_filter
        
    if user_filter:
        matching_users = list(db.users.find({
            "$or": [
                {"name": {"$regex": user_filter, "$options": "i"}},
                {"username": {"$regex": user_filter, "$options": "i"}}
            ]
        }))
        user_ids = [u["_id"] for u in matching_users]
        query["user_id"] = {"$in": user_ids}
        
    detections = list(db.emotions.find(query).sort("timestamp", -1))
    
    # Map usernames to detections for easy display
    detections_mapped = []
    for d in detections:
        user = db.users.find_one({"_id": ObjectId(d["user_id"])})
        detections_mapped.append({
            "id": str(d["_id"]),
            "username": user["username"] if user else "Deleted User",
            "emotion": d["emotion"],
            "confidence": d["confidence"],
            "timestamp": d["timestamp"],
            "image_path": d.get("image_path", "")
        })
        
    return render_template('admin/detections.html', 
                           detections=detections_mapped, 
                           emotions=EMOTIONS,
                           user_filter=user_filter,
                           emotion_filter=emotion_filter)

# Start script
if __name__ == '__main__':
    # Make sure subfolders exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['COVER_FOLDER'], exist_ok=True)
    os.makedirs(app.config['SONG_FOLDER'], exist_ok=True)
    
    # Run
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'True') == 'True'
    app.run(host='0.0.0.0', port=port, debug=debug)
