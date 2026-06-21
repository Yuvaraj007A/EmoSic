// Global Music Player State
let playlist = [];
let currentSongIndex = -1;
let isPlaying = false;
let audioPlayer = null;

// Initialize components when DOM loads
document.addEventListener('DOMContentLoaded', () => {
    audioPlayer = document.getElementById('global-audio-element');
    if (audioPlayer) {
        // Wire up audio event listeners
        audioPlayer.addEventListener('timeupdate', updateProgress);
        audioPlayer.addEventListener('durationchange', setDuration);
        audioPlayer.addEventListener('ended', handleSongEnded);
        
        // Load volume from local storage or set default
        const savedVolume = localStorage.getItem('player-volume') || 80;
        const volumeControl = document.getElementById('player-volume-control');
        if (volumeControl) {
            volumeControl.value = savedVolume;
            audioPlayer.volume = savedVolume / 100;
        }
    }
});

// Play a specific song and load the playlist
function playSong(songId, songTitle, songArtist, songUrl, songCover, isFav, currentPlaylist = []) {
    const playerContainer = document.getElementById('global-player');
    if (!playerContainer) return;
    
    // Show player
    playerContainer.style.display = 'flex';
    
    // Update playlist queue
    if (currentPlaylist.length > 0) {
        playlist = currentPlaylist;
        currentSongIndex = playlist.findIndex(s => s.id === songId);
    } else {
        // Fallback: build single-item playlist if none supplied
        playlist = [{ id: songId, title: songTitle, artist: songArtist, audio_url: songUrl, cover_image: songCover, is_favorite: isFav }];
        currentSongIndex = 0;
    }
    
    loadAndPlaySong(playlist[currentSongIndex]);
}

// Internal helper to load and trigger audio element
function loadAndPlaySong(song) {
    if (!audioPlayer) return;
    
    // Update UI elements
    document.getElementById('player-song-title').innerText = song.title;
    document.getElementById('player-song-artist').innerText = song.artist;
    document.getElementById('player-song-cover').src = song.cover_image;
    
    // Update Favorite Icon status in Player
    const favBtn = document.getElementById('player-fav-btn');
    if (favBtn) {
        if (song.is_favorite) {
            favBtn.innerHTML = '<i class="fa-solid fa-heart"></i>';
            favBtn.classList.add('active');
        } else {
            favBtn.innerHTML = '<i class="fa-regular fa-heart"></i>';
            favBtn.classList.remove('active');
        }
    }
    
    // Set Audio Source and Play
    audioPlayer.src = song.audio_url;
    audioPlayer.load();
    
    audioPlayer.play()
        .then(() => {
            isPlaying = true;
            updatePlayPauseButton();
            updateCardPlayState(song.id, true);
        })
        .catch(e => {
            console.error("Audio playback error: ", e);
            showToast("Failed to play audio track. Dynamic asset may be missing.", "error");
        });
}

// Toggle Play / Pause state
function togglePlay() {
    if (!audioPlayer || currentSongIndex === -1) return;
    
    if (isPlaying) {
        audioPlayer.pause();
        isPlaying = false;
        updateCardPlayState(playlist[currentSongIndex].id, false);
    } else {
        audioPlayer.play()
            .then(() => {
                isPlaying = true;
                updateCardPlayState(playlist[currentSongIndex].id, true);
            })
            .catch(e => console.error(e));
    }
    updatePlayPauseButton();
}

// Toggle play button icon in bottom control bar
function updatePlayPauseButton() {
    const playBtn = document.getElementById('player-play-btn');
    if (!playBtn) return;
    
    if (isPlaying) {
        playBtn.innerHTML = '<i class="fa-solid fa-circle-pause"></i>';
    } else {
        playBtn.innerHTML = '<i class="fa-solid fa-circle-play"></i>';
    }
}

// Navigate to previous song
function prevSong() {
    if (playlist.length <= 1) return;
    updateCardPlayState(playlist[currentSongIndex].id, false);
    
    currentSongIndex--;
    if (currentSongIndex < 0) {
        currentSongIndex = playlist.length - 1;
    }
    loadAndPlaySong(playlist[currentSongIndex]);
}

// Navigate to next song
function nextSong() {
    if (playlist.length <= 1) return;
    updateCardPlayState(playlist[currentSongIndex].id, false);
    
    currentSongIndex = (currentSongIndex + 1) % playlist.length;
    loadAndPlaySong(playlist[currentSongIndex]);
}

// Handle auto-progress when track ends
function handleSongEnded() {
    if (playlist.length > 1) {
        nextSong();
    } else {
        isPlaying = false;
        updatePlayPauseButton();
        updateCardPlayState(playlist[currentSongIndex].id, false);
    }
}

// Volume Controls
function setVolume() {
    const volumeControl = document.getElementById('player-volume-control');
    if (!audioPlayer || !volumeControl) return;
    
    const vol = volumeControl.value;
    audioPlayer.volume = vol / 100;
    localStorage.setItem('player-volume', vol);
}

// Track Progress Updates
function updateProgress() {
    const progressBar = document.getElementById('player-progress');
    const currentTimeEl = document.getElementById('player-current-time');
    
    if (!audioPlayer || !progressBar) return;
    
    const curTime = audioPlayer.currentTime;
    const duration = audioPlayer.duration;
    
    if (duration) {
        progressBar.value = (curTime / duration) * 100;
        currentTimeEl.innerText = formatTime(curTime);
    }
}

function setDuration() {
    const durationEl = document.getElementById('player-duration');
    if (audioPlayer && durationEl && audioPlayer.duration) {
        durationEl.innerText = formatTime(audioPlayer.duration);
    }
}

function seekAudio() {
    const progressBar = document.getElementById('player-progress');
    if (!audioPlayer || !progressBar || !audioPlayer.duration) return;
    
    const targetTime = (progressBar.value / 100) * audioPlayer.duration;
    audioPlayer.currentTime = targetTime;
}

// Format seconds into MM:SS format
function formatTime(secs) {
    const min = Math.floor(secs / 60);
    const sec = Math.floor(secs % 60);
    return `${min.toString().padStart(2, '0')}:${sec.toString().padStart(2, '0')}`;
}

// Favorite endpoint triggers
function toggleFavorite(songIdInput = null) {
    const songId = songIdInput || (playlist[currentSongIndex] ? playlist[currentSongIndex].id : null);
    if (!songId) return;
    
    const isCurrentlyFav = songIdInput 
        ? document.getElementById(`fav-icon-${songId}`).classList.contains('fa-solid')
        : document.getElementById('player-fav-btn').classList.contains('active');
        
    const endpoint = isCurrentlyFav ? `/favorites/remove/${songId}` : `/favorites/add/${songId}`;
    
    fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            // Update cache inside current loaded playlist item
            const listSong = playlist.find(s => s.id === songId);
            if (listSong) {
                listSong.is_favorite = !isCurrentlyFav;
            }
            
            // Sync current active player button
            if (playlist[currentSongIndex] && playlist[currentSongIndex].id === songId) {
                const favBtn = document.getElementById('player-fav-btn');
                if (favBtn) {
                    if (listSong.is_favorite) {
                        favBtn.innerHTML = '<i class="fa-solid fa-heart"></i>';
                        favBtn.classList.add('active');
                    } else {
                        favBtn.innerHTML = '<i class="fa-regular fa-heart"></i>';
                        favBtn.classList.remove('active');
                    }
                }
            }
            
            // Sync card button on page
            const cardFavIcon = document.getElementById(`fav-icon-${songId}`);
            if (cardFavIcon) {
                if (listSong.is_favorite) {
                    cardFavIcon.className = 'fa-solid fa-heart';
                    cardFavIcon.parentElement.classList.add('active');
                } else {
                    cardFavIcon.className = 'fa-regular fa-heart';
                    cardFavIcon.parentElement.classList.remove('active');
                }
            }
            
            showToast(data.message, 'success');
        } else {
            showToast(data.message, 'error');
        }
    })
    .catch(err => {
        console.error(err);
        showToast("Error updating favorites.", 'error');
    });
}

// Synchronize song card play states in view lists
function updateCardPlayState(songId, playState) {
    const cardPlayBtn = document.getElementById(`card-play-${songId}`);
    if (cardPlayBtn) {
        if (playState) {
            cardPlayBtn.innerHTML = '<i class="fa-solid fa-circle-pause play-icon-btn"></i>';
        } else {
            cardPlayBtn.innerHTML = '<i class="fa-solid fa-circle-play play-icon-btn"></i>';
        }
    }
}
