#!/usr/bin/env python3
"""Comprehensive serial connection test for Teensy LED Matrix"""

import serial
import serial.tools.list_ports
import time
import sys
import numpy as np
import argparse

def find_teensy_ports():
    """Find all potential Teensy serial ports"""
    ports = serial.tools.list_ports.comports()
    teensy_ports = []
    
    print("Available serial ports:")
    for p in ports:
        print(f"  {p.device}: {p.description}")
        if 'Teensy' in p.description or 'USB Serial' in p.description or 'ttyACM' in p.device:
            teensy_ports.append(p.device)
    
    return teensy_ports

def test_basic_connection(port, baud_rate=2000000):
    """Test basic serial connection at specified baud rate"""
    try:
        ser = serial.Serial(port, baud_rate, timeout=0.5)
        print(f"✓ Connected to {port} at {baud_rate:,} bps")
        
        # Check for any existing data
        time.sleep(0.1)
        if ser.in_waiting:
            data = ser.read(ser.in_waiting)
            print(f"  Found {len(data)} bytes in buffer")
        
        # Try mode switch commands
        print("  Testing mode switches...")
        ser.write(b's')  # Streaming mode
        ser.flush()
        time.sleep(0.1)
        
        if ser.in_waiting:
            response = ser.read(ser.in_waiting)
            print(f"  Got response: {len(response)} bytes")
        
        ser.close()
        return True
        
    except serial.SerialException as e:
        print(f"✗ Failed to connect at {baud_rate:,} bps: {e}")
        return False

def test_pattern(port):
    """Send a test pattern to verify display functionality"""
    print("\nSending test pattern...")
    
    try:
        ser = serial.Serial(port, 2000000, timeout=1)
        time.sleep(2)  # Wait for Teensy to initialize
        
        # Switch to streaming mode
        ser.write(b's')
        ser.flush()
        time.sleep(0.5)
        
        # Create test patterns
        patterns = [
            ("Red gradient", create_gradient_pattern([255, 0, 0])),
            ("Green gradient", create_gradient_pattern([0, 255, 0])),
            ("Blue gradient", create_gradient_pattern([0, 0, 255])),
            ("White bars", create_bars_pattern()),
        ]
        
        for name, frame in patterns:
            print(f"  Displaying: {name}")
            send_frame(ser, frame)
            time.sleep(1)
        
        # Switch back to effects mode
        print("  Switching back to effects mode...")
        ser.write(b'e')
        ser.flush()
        
        ser.close()
        print("✓ Test pattern complete")
        return True
        
    except Exception as e:
        print(f"✗ Pattern test failed: {e}")
        return False

def create_gradient_pattern(color_base):
    """Create a horizontal gradient pattern"""
    frame = np.zeros((16, 64, 3), dtype=np.uint8)
    for x in range(64):
        intensity = x / 63.0
        for y in range(16):
            frame[y, x] = [int(c * intensity) for c in color_base]
    return frame

def create_bars_pattern():
    """Create vertical bars pattern"""
    frame = np.zeros((16, 64, 3), dtype=np.uint8)
    for x in range(0, 64, 8):
        for y in range(16):
            for i in range(4):
                if x + i < 64:
                    frame[y, x + i] = [128, 128, 128]
    return frame

def send_frame(ser, frame):
    """Send a frame to the LED matrix"""
    frame_bytes = frame.flatten().tobytes()
    ser.write(b'\xFF\xFE\xFD')  # Frame marker
    ser.write(frame_bytes)
    ser.flush()

def test_multiple_baud_rates(port):
    """Test connection at multiple baud rates"""
    print("\nTesting multiple baud rates...")
    baud_rates = [2000000, 115200, 9600]
    
    for baud in baud_rates:
        if test_basic_connection(port, baud):
            return baud
    
    return None

def main():
    parser = argparse.ArgumentParser(description='Test serial connection to Teensy LED Matrix')
    parser.add_argument('--port', help='Serial port (e.g., /dev/ttyACM0)')
    parser.add_argument('--baud', type=int, default=2000000, help='Baud rate (default: 2000000)')
    parser.add_argument('--pattern', action='store_true', help='Send test pattern to display')
    parser.add_argument('--scan', action='store_true', help='Scan multiple baud rates')
    args = parser.parse_args()
    
    print("Teensy LED Matrix Serial Test\n" + "="*40)
    
    # Find port if not specified
    if args.port:
        port = args.port
        print(f"Using specified port: {port}")
    else:
        teensy_ports = find_teensy_ports()
        if not teensy_ports:
            print("\n✗ No Teensy-like devices found!")
            print("\nTroubleshooting:")
            print("1. Check that Teensy is plugged in")
            print("2. Verify permissions: sudo usermod -a -G dialout $USER")
            print("3. Try pressing the reset button on the Teensy")
            return 1
        
        port = teensy_ports[0]
        print(f"\nUsing detected port: {port}")
    
    # Test connection
    if args.scan:
        working_baud = test_multiple_baud_rates(port)
        if working_baud:
            print(f"\n✓ Best baud rate: {working_baud:,} bps")
        else:
            print("\n✗ Could not connect at any baud rate")
            return 1
    else:
        if not test_basic_connection(port, args.baud):
            return 1
    
    # Optional pattern test
    if args.pattern:
        if not test_pattern(port):
            return 1
    
    print("\n✓ All tests passed!")
    return 0

if __name__ == '__main__':
    sys.exit(main())