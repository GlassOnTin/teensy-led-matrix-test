#!/bin/bash

# Stream YouTube video to LED matrix
# Usage: ./stream_youtube.sh [youtube-url]

URL="${1:-https://www.youtube.com/watch?v=_d-HiBvE9b4}"
VIDEO_FILE="seascape.mp4"

echo "LED Matrix YouTube Streamer"
echo "==========================="

# Check if yt-dlp is installed
if ! command -v yt-dlp &> /dev/null; then
    echo "Installing yt-dlp..."
    pip3 install --user yt-dlp
fi

# Check if video already downloaded
if [ ! -f "$VIDEO_FILE" ]; then
    echo "Downloading video..."
    yt-dlp -f "best[height<=720]" -o "$VIDEO_FILE" "$URL"
    if [ $? -ne 0 ]; then
        echo "Failed to download video. Trying youtube-dl instead..."
        youtube-dl -f "best[height<=720]" -o "$VIDEO_FILE" "$URL"
    fi
fi

# Install Python dependencies if needed
pip3 install --user pyserial numpy opencv-python 2>/dev/null

echo ""
echo "Starting video stream to LED matrix..."
echo "Press Ctrl+C to stop"
echo ""

# Run the video streamer
python3 video_streamer.py "$VIDEO_FILE" --fps 25