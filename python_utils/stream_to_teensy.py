#!/usr/bin/env python3
"""Simple script to stream raw RGB data from stdin to Teensy LED matrix"""

import sys
import time
import os
import signal
from serial_connection import TeensyConnection

# Create connection handler
conn = TeensyConnection()

# Connect to Teensy
if not conn.connect(mode='s'):
    print("Failed to connect to Teensy!")
    sys.exit(1)

# Setup signal handler for clean exit
def signal_handler(sig, frame):
    print("\nCleaning up...")
    conn.close()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

print("Streaming to LED matrix... (Press Ctrl+C to stop)")

frame_size = 64 * 16 * 3  # 64x16 pixels, RGB
frame_count = 0
start_time = time.time()
blackout_columns = 1  # Black out first column of both left panels

try:
    while True:
        # Read frame from stdin
        frame_data = sys.stdin.buffer.read(frame_size)
        if len(frame_data) != frame_size:
            break
        
        # Convert to numpy array to black out columns
        import numpy as np
        frame = np.frombuffer(frame_data, dtype=np.uint8).reshape((16, 64, 3)).copy()
        # Black out first column of both left panels
        frame[0:8, 0:blackout_columns] = 0   # Top-left panel
        frame[8:16, 0:blackout_columns] = 0  # Bottom-left panel
        frame_data = frame.flatten().tobytes()
        
        # Send frame with automatic retry on error
        frame_bytes = b'\xFF\xFE\xFD' + frame_data
        if not conn.write_frame(frame_bytes):
            print(f"\nFailed to write frame {frame_count} - retrying...")
            continue
        frame_count += 1
        
        # Show progress
        if frame_count % 30 == 0:
            elapsed = time.time() - start_time
            fps = frame_count / elapsed if elapsed > 0 else 0
            print(f"Frames: {frame_count}, FPS: {fps:.1f}", end='\r')
        
        # Maintain frame rate
        target_time = frame_count / 30.0
        actual_time = time.time() - start_time
        if target_time > actual_time:
            time.sleep(target_time - actual_time)

except KeyboardInterrupt:
    print("\nStopped by user")
except Exception as e:
    print(f"\nError: {e}")
finally:
    # Clean up connection
    print(f"\nTotal frames streamed: {frame_count}")
    conn.close()