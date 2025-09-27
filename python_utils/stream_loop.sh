#!/bin/bash
# Continuous loop streaming from YouTube to LED Matrix

URL="$1"
QUALITY="${2:-240p}"  # Default to 240p for faster streaming
GAMMA="${3:-1.4}"
CONTRAST="${4:-1.3}"

# Set quality format
case $QUALITY in
    144p) FORMAT="worst[height<=144]" ;;
    240p) FORMAT="worst[height<=240]" ;;
    360p) FORMAT="best[height<=360]" ;;
    480p) FORMAT="best[height<=480]" ;;
    *) FORMAT="worst[height<=240]" ;;
esac

echo "Streaming YouTube in continuous loop to LED Matrix"
echo "URL: $URL"
echo "Quality: $QUALITY, Gamma: $GAMMA, Contrast: $CONTRAST"
echo "Press Ctrl+C to stop"

cd ~/teensy-led-matrix-test
source venv/bin/activate

# Continuous loop
while true; do
    echo "Starting stream..."
    
    # Stream with yt-dlp -> ffmpeg -> python
    yt-dlp --cookies-from-browser chrome -f "$FORMAT" "$URL" -o - 2>/dev/null | \
    ffmpeg -i pipe:0 \
        -vf "scale=64:16:force_original_aspect_ratio=decrease,pad=64:16:(ow-iw)/2:(oh-ih)/2,eq=gamma=$GAMMA:contrast=$CONTRAST" \
        -r 30 -f rawvideo -pix_fmt rgb24 - 2>/dev/null | \
    python3 python_utils/stream_to_teensy.py
    
    echo "Stream ended, restarting..."
    sleep 1
done