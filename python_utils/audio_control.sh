#!/bin/bash
# Simple control script for audio visualizer

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/../venv/bin/python"
AUDIO_VIZ="$SCRIPT_DIR/audio_visualizer.py"
PID_FILE="/tmp/audio_viz.pid"

start_viz() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "Audio visualizer already running with PID $PID"
            return 1
        fi
    fi
    
    MODE=${1:-fft}
    DURATION=${2:-30}
    COLOR=${3:-fire}
    GAIN=${4:-3.0}
    
    echo "Starting audio visualizer..."
    echo "Mode: $MODE, Duration: ${DURATION}s, Color: $COLOR, Gain: $GAIN"
    
    # Run in background with timeout
    timeout $DURATION $VENV_PYTHON $AUDIO_VIZ $MODE --color $COLOR --gain $GAIN > /dev/null 2>&1 &
    PID=$!
    echo $PID > "$PID_FILE"
    
    echo "Started with PID $PID (will auto-stop in ${DURATION}s)"
    echo "To stop early: $0 stop"
}

stop_viz() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "Stopping audio visualizer (PID $PID)..."
            kill -TERM $PID 2>/dev/null
            sleep 1
            if ps -p $PID > /dev/null 2>&1; then
                kill -KILL $PID 2>/dev/null
            fi
            rm -f "$PID_FILE"
            echo "Stopped"
        else
            echo "Process not running"
            rm -f "$PID_FILE"
        fi
    else
        echo "No audio visualizer running"
    fi
}

status_viz() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p $PID > /dev/null 2>&1; then
            echo "Audio visualizer running with PID $PID"
        else
            echo "Audio visualizer not running (stale PID file)"
            rm -f "$PID_FILE"
        fi
    else
        echo "Audio visualizer not running"
    fi
}

case "$1" in
    start)
        start_viz $2 $3 $4 $5
        ;;
    stop)
        stop_viz
        ;;
    status)
        status_viz
        ;;
    restart)
        stop_viz
        sleep 1
        start_viz $2 $3 $4 $5
        ;;
    *)
        echo "Usage: $0 {start|stop|status|restart} [mode] [duration] [color] [gain]"
        echo "  mode: fft, oscilloscope, or spectrogram (default: fft)"
        echo "  duration: seconds to run (default: 30)"
        echo "  color: rainbow, fire, ocean, or matrix (default: fire)"
        echo "  gain: audio gain multiplier (default: 3.0)"
        echo ""
        echo "Examples:"
        echo "  $0 start                    # Start with defaults (fft, 30s, fire, 3.0)"
        echo "  $0 start fft 10 rainbow 2.0 # Custom settings"
        echo "  $0 stop                      # Stop the visualizer"
        echo "  $0 status                    # Check if running"
        exit 1
        ;;
esac