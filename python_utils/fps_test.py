#!/usr/bin/env python3
"""
Frame Rate Test - Measures maximum achievable FPS on LED matrix
"""

import time
import numpy as np
from serial_connection import TeensyConnection
import argparse

def run_fps_test(duration=10, pattern='rainbow'):
    """Test maximum frame rate achievable."""
    
    # Connect to Teensy
    conn = TeensyConnection()
    if not conn.connect(mode='s'):
        print("Failed to connect to Teensy!")
        return
    
    print(f"Connected at {conn.baudrate} baud")
    print(f"Testing for {duration} seconds with {pattern} pattern...")
    
    # Frame dimensions
    width, height = 64, 16
    frame_size = width * height * 3
    
    # Statistics
    frame_count = 0
    start_time = time.time()
    last_report = start_time
    
    # Pattern generators
    hue_offset = 0
    
    try:
        while (time.time() - start_time) < duration:
            # Generate frame based on pattern
            if pattern == 'rainbow':
                # Animated rainbow
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                for x in range(width):
                    hue = (x * 4 + hue_offset) % 256
                    # Simple HSV to RGB (approximate)
                    if hue < 85:
                        r = 255 - hue * 3
                        g = hue * 3
                        b = 0
                    elif hue < 170:
                        h = hue - 85
                        r = 0
                        g = 255 - h * 3
                        b = h * 3
                    else:
                        h = hue - 170
                        r = h * 3
                        g = 0
                        b = 255 - h * 3
                    frame[:, x] = [r, g, b]
                hue_offset = (hue_offset + 4) % 256
                
            elif pattern == 'random':
                # Random noise
                frame = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
                
            elif pattern == 'solid':
                # Solid color that changes
                color = [
                    int(127 * (1 + np.sin(frame_count * 0.05))),
                    int(127 * (1 + np.sin(frame_count * 0.05 + 2.09))),
                    int(127 * (1 + np.sin(frame_count * 0.05 + 4.18)))
                ]
                frame = np.full((height, width, 3), color, dtype=np.uint8)
            
            else:  # strobe
                # Fast black/white strobe
                if frame_count % 2 == 0:
                    frame = np.full((height, width, 3), 255, dtype=np.uint8)
                else:
                    frame = np.zeros((height, width, 3), dtype=np.uint8)
            
            # Send frame
            frame_bytes = b'\xFF\xFE\xFD' + frame.flatten().tobytes()
            if not conn.write_frame(frame_bytes):
                print(f"Write error at frame {frame_count}")
                continue
            
            frame_count += 1
            
            # Report progress every second
            current_time = time.time()
            if current_time - last_report >= 1.0:
                elapsed = current_time - start_time
                fps = frame_count / elapsed
                print(f"Frames: {frame_count:5d} | FPS: {fps:6.1f} | "
                      f"Time: {elapsed:5.1f}s", end='\r')
                last_report = current_time
            
            # No sleep - run as fast as possible
        
        # Final report
        total_time = time.time() - start_time
        avg_fps = frame_count / total_time
        
        print(f"\n\n{'='*50}")
        print(f"FPS TEST RESULTS")
        print(f"{'='*50}")
        print(f"Total frames:    {frame_count}")
        print(f"Total time:      {total_time:.2f} seconds")
        print(f"Average FPS:     {avg_fps:.1f}")
        print(f"Frame time:      {1000/avg_fps:.2f} ms")
        print(f"Data rate:       {avg_fps * frame_size / 1024:.1f} KB/s")
        print(f"{'='*50}")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description='Test LED matrix frame rate')
    parser.add_argument('--duration', type=int, default=10, 
                       help='Test duration in seconds (default: 10)')
    parser.add_argument('--pattern', choices=['rainbow', 'random', 'solid', 'strobe'],
                       default='rainbow', help='Test pattern (default: rainbow)')
    
    args = parser.parse_args()
    run_fps_test(args.duration, args.pattern)

if __name__ == "__main__":
    main()