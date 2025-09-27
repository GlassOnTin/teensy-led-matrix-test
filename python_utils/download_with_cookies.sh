#!/bin/bash

echo "YouTube Video Downloader with Authentication"
echo "==========================================="
echo ""
echo "Option 1: Use Firefox cookies (if you're logged into YouTube in Firefox):"
echo "  yt-dlp --cookies-from-browser firefox <video-url>"
echo ""
echo "Option 2: Use Chrome cookies (if you're logged into YouTube in Chrome):"
echo "  yt-dlp --cookies-from-browser chrome <video-url>"
echo ""
echo "Option 3: Export cookies manually using browser extension"
echo ""

URL="${1:-https://www.youtube.com/watch?v=_d-HiBvE9b4}"

# Try Firefox first
echo "Attempting download with Firefox cookies..."
cd ~/teensy-led-matrix-test
source venv/bin/activate

yt-dlp --cookies-from-browser firefox -f "best[height<=720]" -o "seascape.mp4" "$URL" 2>/dev/null

if [ $? -eq 0 ]; then
    echo "Download successful!"
    echo "Now streaming to LED matrix..."
    python3 video_streamer.py seascape.mp4 --port /dev/ttyACM0 --fps 25
else
    echo "Firefox cookies failed. Trying Chrome..."
    yt-dlp --cookies-from-browser chrome -f "best[height<=720]" -o "seascape.mp4" "$URL" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo "Download successful!"
        echo "Now streaming to LED matrix..."
        python3 video_streamer.py seascape.mp4 --port /dev/ttyACM0 --fps 25
    else
        echo ""
        echo "Automatic cookie extraction failed."
        echo ""
        echo "Manual option:"
        echo "1. Install a cookie export extension in your browser"
        echo "2. Export cookies to cookies.txt"
        echo "3. Run: yt-dlp --cookies cookies.txt -f 'best[height<=720]' -o 'seascape.mp4' '$URL'"
        echo ""
        echo "Alternative: Try a different video or use local files"
    fi
fi