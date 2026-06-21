---
title: EmoSic
emoji: 🎵
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# EmoSic: Emotion-Based Music Recommendation System


EmoSic is a production-ready web application that analyzes user facial expressions in real time using webcam capture, predicts their emotional state using an AI model (mini-XCEPTION CNN), and recommends matching music playlists. The system features a modern Dark Mode Glassmorphism layout, user security, analytics curves, and administrative dashboards.

🔗 **Live Demo**: [Hugging Face Space](https://huggingface.co/spaces/Yuvaraj007A/EmoSic)
🌐 **Direct Link (Iframe-free)**: [https://yuvaraj007a-emosic.hf.space](https://yuvaraj007a-emosic.hf.space)

---

## 💻 Tech Stack
* **Frontend**: HTML5, CSS3 (Glassmorphic Stylesheet), Vanilla JavaScript, Chart.js, FontAwesome.
* **Backend**: Flask Web Framework (Python).
* **Database**: MongoDB Atlas or Local Community Server (`pymongo`).
* **AI/ML**: Keras/TensorFlow (mini-XCEPTION model trained on FER-2013).
* **Computer Vision**: OpenCV Haar Cascade (`haarcascade_frontalface_default.xml`).

---

## 📂 Folder Structure

```
emotion_music_system/
├── app.py                     # Main Flask server engine & routes
├── config.py                  # Environment loader & system configurations
├── setup_assets.py            # Automation utility downloading AI weights and XML files
├── requirements.txt           # Python library dependencies
├── .env                       # Secrets (Secret Keys, Mongo Connection Strings)
├── README.md                  # Installation and Setup Instructions (This document)
│
├── models/
│   └── mini_XCEPTION.hdf5     # Pre-trained CNN classifier weights
│
├── haarcascade_files/
│   └── haarcascade_frontalface_default.xml # OpenCV face detector XML
│
├── static/
│   ├── css/
│   │   └── style.css          # Main Glassmorphism Design System CSS
│   ├── js/
│   │   ├── main.js            # Global Audio Player & Favorite callbacks JS
│   │   └── webcam.js          # Webcam capture & overlay bounding boxes JS
│   ├── images/
│   │   └── default_avatar.png # Blank avatar placeholder
│   ├── uploads/               # Cropped face captures
│   ├── covers/                # Album cover images
│   └── songs/                 # MP3 music files
│
└── templates/
    ├── base.html              # Core Layout template (header, global player, toasts)
    ├── landing.html           # Elegant Hero homepage & animations
    ├── login.html             # Secure user log in portal
    ├── register.html          # Registration card with interactive password meter
    ├── forgot_password.html   # OTP wizard password resetting pages
    ├── dashboard.html         # User summary panel and metrics
    ├── profile.html           # Settings panel (profile, upload avatar, download, delete)
    ├── emotion.html           # Camera view, probability sliders, and playlists
    ├── history.html           # Filterable scans log table (CSV/PDF export)
    ├── analytics.html         # User statistics graphs (Doughnut, Line, Radar)
    └── admin/
        ├── dashboard.html     # Administration dashboard curves
        ├── users.html         # User suspensions, roles editing, account search
        ├── songs.html         # CRUD interface for songs registry
        └── detections.html    # System-wide scan audit logs search and filters
```

---

## ⚙️ Setup & Installation Instructions

### Step 1: Clone and Navigate
Navigate into the project directory:
```bash
cd emotion_music_system
```

### Step 2: Set Up Virtual Environment
Create and activate a Python virtual environment:
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
Install requirements:
```bash
pip install -r requirements.txt
```

### Step 4: Run Asset Setup Script
Run the helper setup script. It will generate missing subdirectories, download the Keras `mini_XCEPTION.hdf5` model, download OpenCV's face cascade, and create blank placeholder avatar files:
```bash
python setup_assets.py
```

### Step 5: Configure Environment
Open the `.env` file and set your custom values. Change the database URI connection string to match your MongoDB Atlas configuration (see instructions below) or keep the local connection if you have local MongoDB Community server running.

---

## 🍃 MongoDB Setup Guide

### Option A: MongoDB Atlas (Cloud - Production Ready)
1. **Sign Up / Log In**: Access [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
2. **Create Cluster**: Deploy a free tier cluster (Shared M0 Sandbox). Select your preferred cloud provider and region.
3. **Database Access User**:
   * Under **Security** in the left sidebar, click **Database Access**.
   * Click **Add New Database User**.
   * Choose **Password Authentication**, set a Username and Password, and grant the user **Read and write to any database** privilege.
4. **Network Access (IP Whitelist)**:
   * Click **Network Access** in the left sidebar.
   * Click **Add IP Address**.
   * For development, select **Allow Access From Anywhere** (Adds IP `0.0.0.0/0`) or input your specific IP. Click **Confirm**.
5. **Get Connection String**:
   * Go to **Database** (or clusters) screen and click **Connect**.
   * Select **Drivers** (or Connect your application).
   * Copy the connection string. It will look like this:
     `mongodb+srv://<username>:<password>@cluster0.mongodb.net/?retryWrites=true&w=majority`
6. **Configure .env**:
   * Open the `.env` file.
   * Replace `MONGO_URI` value with your connection string. Make sure to replace `<username>` and `<password>` with the credentials you created in step 3, and set the target database name to `emotion_music_db`:
     `MONGO_URI=mongodb+srv://user123:mypassword@cluster0.mongodb.net/emotion_music_db?retryWrites=true&w=majority`

### Option B: MongoDB Community Server (Local)
1. **Download & Install**: Download the installer from the [MongoDB Download Center](https://www.mongodb.com/try/download/community) and follow installation instructions.
2. **Run MongoDB Service**: Make sure the local MongoDB server process is running (Default port: `27017`).
3. **Configure .env**:
   * Use the local connection string already supplied in `.env` default:
     `MONGO_URI=mongodb://localhost:27017/emotion_music_db`

---

## 🚀 Running the Application

Start the Flask server:
```bash
python app.py
```
Open your browser and navigate to `http://localhost:5000`.

Standard users can sign up using the **Register** form.

### 🧪 Testing Forgot Password OTP
To test the password recovery wizard without configuring an SMTP mail server:
1. Input your email on the **Forgot Password** screen and submit.
2. An OTP token will be generated. Look directly at your **Python terminal console logs/standard output** where the Flask server is running. You will see a log printout like:
   ```
   ==========================================
   [OTP REQUEST] Password reset requested for: email@example.com
   [OTP CODE] Verification OTP: 456729
   ==========================================
   ```
3. Enter that 6-digit code on the verification screen to reset your password.

---

## 🐳 Docker & Hugging Face Spaces Deployment

EmoSic is optimized to run inside Docker containers and is pre-configured to be hosted on **Hugging Face Spaces**.

### Hugging Face Space Settings:
* **SDK**: `docker` (uses the root `Dockerfile`)

### Deployment Steps:
1. **Create Space**: On Hugging Face, create a new Space, choose **Docker** as the SDK, and select **Blank**.
2. **Environment Secrets**: Under the Space's **Settings** tab, add your environment secrets:
   * `MONGO_URI`: Your MongoDB Atlas connection string (Atlas cloud is required for persistence).
   * `SECRET_KEY`: A secure random string for signing user sessions.
3. **Session Cookie Security**: The application dynamically handles session cookies (`SameSite=None` and `Secure=True`) when running in the Hugging Face iframe so that user logins persist correctly.

---

## 📦 Git Large File Storage (LFS)

This project contains large binary assets (the pre-trained model `mini_XCEPTION.hdf5` and several default `.mp3` tracks). These are managed using **Git LFS** to keep the Git history small and optimized.

If you are cloning this repository on a new system:
1. Ensure Git LFS is installed.
2. Initialize and pull LFS objects:
   ```bash
   git lfs install
   git lfs pull
   ```

