#!/bin/bash
# Continuous VU meter runner with auto-restart

echo "Starting continuous VU meter on LED matrix..."
echo "Press Ctrl+C to stop"

# Trap to handle cleanup
cleanup() {
    echo -e "\nStopping VU meter..."
    exit 0
}
trap cleanup SIGINT SIGTERM

# Run VU meter in a loop, restarting if it exits
while true; do
    echo "Starting VU meter ($(date))"
    
    # Run the VU meter with classic palette for clear red zone visibility
    # Device 29 is default - should route through PipeWire
    # Gain of 2.0 allows reaching 0dB with normal audio levels
    ./venv/bin/python python_utils/vu_meter.py --device 29 --palette classic --gain 2.0
    
    # Check exit code
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "VU meter exited normally"
    else
        echo "VU meter crashed with exit code $EXIT_CODE"
    fi
    
    echo "Restarting in 2 seconds..."
    sleep 2
done