#!/usr/bin/env python3
"""Test script to verify spectrogram is actually displaying on LED matrix"""

import sys
import numpy as np
import serial
import serial.tools.list_ports
import time
import argparse

def find_teensy():
    """Find Teensy serial port"""
    ports = serial.tools.list_ports.comports()
    for p in ports:
        if any(x in p.description for x in ['Teensy', 'USB Serial', 'ACM']):
            print(f"Found device on {p.device}: {p.description}")
            return p.device
    return None

def send_test_pattern(ser, pattern_type="bars"):
    """Send a test pattern to verify display"""
    width = 64
    height = 16
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    
    if pattern_type == "bars":
        # Vertical bars of increasing intensity
        print("Sending vertical bar pattern (should see 8 bars of increasing brightness)")
        for x in range(width):
            intensity = int((x / width) * 255)
            for y in range(height):
                frame[y, x] = [intensity, intensity, intensity]
    
    elif pattern_type == "frequency":
        # Horizontal frequency bands
        print("Sending horizontal frequency bands (should see 16 horizontal lines)")
        for y in range(height):
            intensity = int((y / height) * 255)
            for x in range(width):
                # Different colors for each band
                if y < 5:  # Low frequencies - red
                    frame[y, x] = [intensity, 0, 0]
                elif y < 10:  # Mid frequencies - green
                    frame[y, x] = [0, intensity, 0]
                else:  # High frequencies - blue
                    frame[y, x] = [0, 0, intensity]
    
    elif pattern_type == "sweep":
        # Moving vertical line
        print("Sending sweep pattern (should see a white line moving left to right)")
        for pos in range(width):
            frame.fill(0)
            for y in range(height):
                frame[y, pos] = [255, 255, 255]
            
            # Send frame
            frame_bytes = frame.flatten().tobytes()
            ser.write(b'\xFF\xFE\xFD')  # Frame marker
            ser.write(frame_bytes)
            ser.flush()
            time.sleep(0.05)
        return  # Already sent frames in loop
    
    elif pattern_type == "corners":
        # Test corners to verify orientation
        print("Sending corner test (should see colored corners)")
        # Top-left - red
        frame[0:3, 0:8] = [255, 0, 0]
        # Top-right - green
        frame[0:3, 56:64] = [0, 255, 0]
        # Bottom-left - blue
        frame[13:16, 0:8] = [0, 0, 255]
        # Bottom-right - white
        frame[13:16, 56:64] = [255, 255, 255]
        # Center cross - yellow
        frame[7:9, :] = [255, 255, 0]
        frame[:, 31:33] = [255, 255, 0]
    
    # Send the frame
    frame_bytes = frame.flatten().tobytes()
    ser.write(b'\xFF\xFE\xFD')  # Frame marker
    ser.write(frame_bytes)
    ser.flush()

def test_audio_response(ser, duration=10):
    """Test with generated audio tones"""
    try:
        import sounddevice as sd
    except ImportError:
        print("sounddevice not installed, skipping audio test")
        return
    
    print(f"\nTesting audio response for {duration} seconds...")
    print("Generating test tones at different frequencies")
    print("You should see activity at different vertical positions")
    
    sample_rate = 44100
    
    # Generate and play different frequency sweeps
    frequencies = [100, 200, 400, 800, 1600, 3200, 6400]
    
    for freq in frequencies:
        print(f"Playing {freq}Hz tone...")
        t = np.linspace(0, 1, sample_rate)
        tone = 0.3 * np.sin(2 * np.pi * freq * t)
        sd.play(tone, sample_rate)
        sd.wait()
        time.sleep(0.5)
    
    print("Audio test complete")

def interactive_test(ser):
    """Interactive test mode"""
    print("\n=== INTERACTIVE TEST MODE ===")
    print("Commands:")
    print("  1 - Vertical bars (gradient)")
    print("  2 - Frequency bands (colored)")
    print("  3 - Sweep (moving line)")
    print("  4 - Corner test (orientation)")
    print("  5 - All black")
    print("  6 - All white")
    print("  q - Quit")
    print("=" * 30)
    
    while True:
        cmd = input("\nEnter command: ").strip().lower()
        
        if cmd == '1':
            send_test_pattern(ser, "bars")
        elif cmd == '2':
            send_test_pattern(ser, "frequency")
        elif cmd == '3':
            send_test_pattern(ser, "sweep")
        elif cmd == '4':
            send_test_pattern(ser, "corners")
        elif cmd == '5':
            print("Sending all black")
            frame = np.zeros((16, 64, 3), dtype=np.uint8)
            ser.write(b'\xFF\xFE\xFD')
            ser.write(frame.flatten().tobytes())
            ser.flush()
        elif cmd == '6':
            print("Sending all white (BRIGHT!)")
            frame = np.full((16, 64, 3), 100, dtype=np.uint8)  # Not full 255 for safety
            ser.write(b'\xFF\xFE\xFD')
            ser.write(frame.flatten().tobytes())
            ser.flush()
        elif cmd == 'q':
            break
        else:
            print("Unknown command")
    
    print("Exiting interactive mode")

def main():
    parser = argparse.ArgumentParser(description='Test LED matrix display')
    parser.add_argument('--port', help='Serial port')
    parser.add_argument('--pattern', choices=['bars', 'frequency', 'sweep', 'corners', 'all'],
                       default='all', help='Test pattern to display')
    parser.add_argument('--interactive', action='store_true',
                       help='Interactive test mode')
    parser.add_argument('--audio', action='store_true',
                       help='Test with audio tones')
    
    args = parser.parse_args()
    
    # Find serial port
    port = args.port or find_teensy()
    if not port:
        print("No Teensy found!")
        return 1
    
    # Connect
    print(f"Connecting to {port}...")
    try:
        ser = serial.Serial(port, 2000000, timeout=1)
        print("Connected at 2Mbps")
    except Exception as e:
        print(f"Failed to connect: {e}")
        return 1
    
    # Wait for device
    time.sleep(2)
    
    # Clear buffers and switch to streaming mode
    ser.reset_input_buffer()
    ser.reset_output_buffer()
    ser.write(b's')  # Streaming mode
    ser.flush()
    time.sleep(0.5)
    
    print("\n=== LED MATRIX DISPLAY TEST ===")
    print("Watch the LED matrix to verify patterns are displaying correctly")
    print("=" * 40)
    
    try:
        if args.interactive:
            interactive_test(ser)
        elif args.audio:
            test_audio_response(ser, 10)
        elif args.pattern == 'all':
            # Run all test patterns
            patterns = ['bars', 'frequency', 'corners', 'sweep']
            for pattern in patterns:
                print(f"\nTest: {pattern}")
                send_test_pattern(ser, pattern)
                time.sleep(3)
        else:
            send_test_pattern(ser, args.pattern)
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\nInterrupted")
    finally:
        # Return to effects mode
        ser.write(b'e')
        time.sleep(0.1)
        ser.close()
        print("\nTest complete - returned to effects mode")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())