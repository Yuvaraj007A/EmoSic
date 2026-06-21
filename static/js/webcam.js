let localStream = null;
let captureInterval = null;
let isCamActive = false;
let isScanning = false;
let currentRecommendations = [];

const EMOTION_LIST = ["angry", "disgust", "scared", "happy", "sad", "surprised", "neutral"];

// Start Camera Stream
function startCamera() {
    const video = document.getElementById('webcam-video');
    if (!video) return;
    
    // Clear old state
    clearBoundingBox();
    
    navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } })
        .then(stream => {
            localStream = stream;
            video.srcObject = stream;
            isCamActive = true;
            
            // Toggle buttons visibility
            document.getElementById('btn-start-cam').style.display = 'none';
            document.getElementById('btn-stop-cam').style.display = 'inline-flex';
            document.getElementById('btn-capture-mood').removeAttribute('disabled');
            document.getElementById('btn-live-toggle').removeAttribute('disabled');
            
            showToast("Camera stream activated successfully.", "success");
        })
        .catch(err => {
            console.error("Camera access error: ", err);
            showToast("Failed to access camera. Check your permissions.", "error");
        });
}

// Stop Camera Stream
function stopCamera() {
    const video = document.getElementById('webcam-video');
    if (!video) return;
    
    stopLiveScan();
    clearBoundingBox();
    
    if (localStream) {
        localStream.getTracks().forEach(track => track.stop());
        video.srcObject = null;
    }
    
    isCamActive = false;
    
    // Toggle buttons
    document.getElementById('btn-start-cam').style.display = 'inline-flex';
    document.getElementById('btn-stop-cam').style.display = 'none';
    document.getElementById('btn-capture-mood').setAttribute('disabled', 'true');
    document.getElementById('btn-live-toggle').setAttribute('disabled', 'true');
    
    showToast("Camera stream stopped.", "info");
}

// Scan expression
function captureAndDetect() {
    if (!isCamActive || isScanning) return;
    
    const video = document.getElementById('webcam-video');
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    
    const ctx = canvas.getContext('2d');
    // Mirror capture to match mirrored webcam video
    ctx.translate(canvas.width, 0);
    ctx.scale(-1, 1);
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    
    const base64Image = canvas.toDataURL('image/jpeg');
    
    // Show Scanning Loader
    document.getElementById('scan-overlay-loader').classList.add('active');
    isScanning = true;
    
    fetch('/detect', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ image: base64Image })
    })
    .then(res => res.json())
    .then(data => {
        document.getElementById('scan-overlay-loader').classList.remove('active');
        isScanning = false;
        
        if (data.success) {
            if (data.face_detected) {
                // Update Bounding Box
                drawFaceBox(data.box, video);
                
                // Update Emotion values
                document.getElementById('predicted-emotion-label').innerText = data.emotion.toUpperCase();
                document.getElementById('confidence-score-label').innerText = `${(data.confidence * 100).toFixed(1)}%`;
                document.getElementById('scan-timestamp-label').innerText = new Date().toLocaleTimeString();
                
                // Update Probability Bars
                EMOTION_LIST.forEach(em => {
                    const bar = document.getElementById(`prob-bar-${em}`);
                    const percent = document.getElementById(`prob-percent-${em}`);
                    if (bar && percent) {
                        const val = (data.probabilities[em] * 100).toFixed(1);
                        bar.style.width = `${val}%`;
                        percent.innerText = `${val}%`;
                    }
                });
                
                // Update Song recommendations
                renderSongs(data.songs);
                showToast(`Expression scan completed. Detected mood: ${data.emotion}`, "success");
            } else {
                clearBoundingBox();
                showToast("No face detected in video frame. Reposition yourself.", "warning");
            }
        } else {
            showToast(`Detection error: ${data.error}`, "error");
        }
    })
    .catch(err => {
        document.getElementById('scan-overlay-loader').classList.remove('active');
        isScanning = false;
        console.error(err);
        showToast("Error communicating with AI detection engine.", "error");
    });
}

// Draw Face Box
function drawFaceBox(box, video) {
    const boxOverlay = document.getElementById('face-bounding-box');
    if (!boxOverlay) return;
    
    const [x, y, w, h] = box;
    
    // Scale parameters mapping video pixels to client width/height
    const scaleX = video.clientWidth / video.videoWidth;
    const scaleY = video.clientHeight / video.videoHeight;
    
    // Face box overlay details
    boxOverlay.style.left = `${x * scaleX}px`;
    boxOverlay.style.top = `${y * scaleY}px`;
    boxOverlay.style.width = `${w * scaleX}px`;
    boxOverlay.style.height = `${h * scaleY}px`;
    boxOverlay.style.display = 'block';
}

function clearBoundingBox() {
    const boxOverlay = document.getElementById('face-bounding-box');
    if (boxOverlay) {
        boxOverlay.style.display = 'none';
    }
}

// Toggle Live/Continuous Scan Mode
function toggleLiveScan() {
    const btn = document.getElementById('btn-live-toggle');
    if (!btn) return;
    
    if (captureInterval) {
        stopLiveScan();
    } else {
        startLiveScan();
    }
}

function startLiveScan() {
    const btn = document.getElementById('btn-live-toggle');
    btn.innerHTML = '<i class="fa-solid fa-pause"></i> Pause Continuous';
    btn.classList.replace('btn-secondary', 'btn-primary');
    
    // Initial capture
    captureAndDetect();
    
    // Set periodic scans every 5 seconds
    captureInterval = setInterval(captureAndDetect, 5000);
    showToast("Continuous Scan Mode activated.", "info");
}

function stopLiveScan() {
    const btn = document.getElementById('btn-live-toggle');
    if (!btn || !captureInterval) return;
    
    clearInterval(captureInterval);
    captureInterval = null;
    
    btn.innerHTML = '<i class="fa-solid fa-play"></i> Continuous Mode';
    btn.classList.replace('btn-primary', 'btn-secondary');
    showToast("Continuous Scan Mode disabled.", "info");
}

// Render Song Cards dynamically
function renderSongs(songs) {
    const container = document.getElementById('recommended-songs-container');
    if (!container) return;
    
    currentRecommendations = songs;
    
    if (songs.length === 0) {
        container.innerHTML = `
            <div style="grid-column: span 3; text-align: center; padding: 3rem; color: var(--text-secondary);">
                <i class="fa-solid fa-music-slash" style="font-size: 3rem; margin-bottom: 1rem;"></i>
                <p>No songs found registered for this emotion. Admin can add songs via the dashboard.</p>
            </div>
        `;
        return;
    }
    
    let html = '';
    songs.forEach((song, idx) => {
        const isFavClass = song.is_favorite ? 'active' : '';
        const heartIcon = song.is_favorite ? 'fa-solid fa-heart' : 'fa-regular fa-heart';
        
        html += `
            <div class="glass-container song-card" id="song-card-${song.id}">
                <div class="song-cover-wrapper">
                    <img class="song-cover" src="${song.cover_image}" alt="${song.title} Cover">
                    <div class="song-overlay-play" id="card-play-${song.id}" onclick="triggerGlobalPlay('${song.id}')">
                        <i class="fa-solid fa-circle-play play-icon-btn"></i>
                    </div>
                </div>
                <div class="song-details">
                    <h4 class="song-title">${song.title}</h4>
                    <p class="song-artist">${song.artist}</p>
                </div>
                <div class="song-actions">
                    <button class="action-btn ${isFavClass}" onclick="toggleFavorite('${song.id}')">
                        <i id="fav-icon-${song.id}" class="${heartIcon}"></i>
                    </button>
                    <a href="${song.audio_url}" download="${song.title} - ${song.artist}" class="action-btn" title="Download">
                        <i class="fa-solid fa-download"></i>
                    </a>
                    <button class="action-btn" onclick="shareSong('${song.title}', '${song.artist}')" title="Share">
                        <i class="fa-solid fa-share-nodes"></i>
                    </button>
                </div>
            </div>
        `;
    });
    
    container.innerHTML = html;
}

// Trigger Global Play Handler
function triggerGlobalPlay(songId) {
    const song = currentRecommendations.find(s => s.id === songId);
    if (!song) return;
    
    // Call global player defined in main.js
    playSong(song.id, song.title, song.artist, song.audio_url, song.cover_image, song.is_favorite, currentRecommendations);
}

// Share Handler
function shareSong(title, artist) {
    if (navigator.share) {
        navigator.share({
            title: `Recommended Song: ${title}`,
            text: `Check out "${title}" by ${artist} on EmoSic!`,
            url: window.location.origin
        }).catch(err => console.error(err));
    } else {
        // Fallback: clipboard copy
        navigator.clipboard.writeText(`Recommended song: "${title}" by ${artist}. Discover your emotional music match at EmoSic!`);
        showToast("Share text copied to clipboard!", "success");
    }
}
