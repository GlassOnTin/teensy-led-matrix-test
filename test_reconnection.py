#!/usr/bin/env python3
"""Test serial reconnection and state management."""

import sys
import os
import time
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python_utils'))

from serial_connection import TeensyConnection

def test_basic_connection():
    """Test basic connection establishment."""
    print("=" * 60)
    print("Test 1: Basic Connection")
    print("=" * 60)

    conn = TeensyConnection()
    if conn.connect():
        print("✅ Initial connection successful")
        conn.close()
        return True
    else:
        print("❌ Initial connection failed")
        return False

def test_mode_switching():
    """Test switching between streaming and effects mode."""
    print("\n" + "=" * 60)
    print("Test 2: Mode Switching")
    print("=" * 60)

    conn = TeensyConnection()

    # Connect in streaming mode
    print("Connecting in streaming mode...")
    if not conn.connect(mode='s'):
        print("❌ Failed to connect")
        return False
    print("✅ Connected in streaming mode")
    time.sleep(1)

    # Switch to effects mode
    print("Switching to effects mode...")
    if conn.set_mode('e'):
        print("✅ Switched to effects mode")
    else:
        print("❌ Failed to switch to effects mode")
    time.sleep(1)

    # Switch back to streaming mode
    print("Switching back to streaming mode...")
    if conn.set_mode('s'):
        print("✅ Switched back to streaming mode")
    else:
        print("❌ Failed to switch to streaming mode")

    conn.close()
    return True

def test_reconnection():
    """Test reconnection after manual disconnect."""
    print("\n" + "=" * 60)
    print("Test 3: Reconnection")
    print("=" * 60)

    conn = TeensyConnection()

    # Initial connection
    print("Initial connection...")
    if not conn.connect():
        print("❌ Initial connection failed")
        return False
    print("✅ Initial connection successful")

    # Close connection
    print("Closing connection...")
    conn.close()
    print("✅ Connection closed")
    time.sleep(1)

    # Reconnect
    print("Reconnecting...")
    if conn.connect():
        print("✅ Reconnection successful")
        conn.close()
        return True
    else:
        print("❌ Reconnection failed")
        return False

def test_device_lock():
    """Test device locking mechanism."""
    print("\n" + "=" * 60)
    print("Test 4: Device Lock")
    print("=" * 60)

    # First connection
    conn1 = TeensyConnection()
    print("First connection acquiring lock...")
    if not conn1.connect():
        print("❌ First connection failed")
        return False
    print("✅ First connection has lock")

    # Try second connection (should fail)
    conn2 = TeensyConnection()
    print("Second connection attempting to acquire lock...")
    if conn2.connect():
        print("❌ Second connection succeeded (lock not working!)")
        conn2.close()
        conn1.close()
        return False
    else:
        print("✅ Second connection blocked (lock working)")

    # Close first connection
    print("Releasing first connection lock...")
    conn1.close()
    print("✅ Lock released")
    time.sleep(0.5)

    # Now second connection should work
    print("Second connection attempting again...")
    if conn2.connect():
        print("✅ Second connection acquired lock after release")
        conn2.close()
        return True
    else:
        print("❌ Second connection failed even after lock release")
        return False

def test_usb_replug_prompt():
    """Prompt user to test USB unplug/replug."""
    print("\n" + "=" * 60)
    print("Test 5: USB Unplug/Replug (Manual)")
    print("=" * 60)

    conn = TeensyConnection()

    # Initial connection
    print("Establishing initial connection...")
    if not conn.connect():
        print("❌ Initial connection failed")
        return False
    print("✅ Connected successfully")

    # Send test pattern
    print("Sending test pattern...")
    frame = bytes([0xFF, 0xFE, 0xFD] + [255, 0, 0] * 1024)
    if conn.write_frame(frame):
        print("✅ Test pattern sent")

    input("\n⚠️  Please UNPLUG the USB cable now, then press Enter...")

    # Try to send (should fail)
    print("Attempting to send frame (should fail)...")
    if not conn.write_frame(frame):
        print("✅ Write failed as expected")

    input("\n⚠️  Please PLUG the USB cable back in, then press Enter...")

    # Wait for device to reappear
    print("Waiting for device to reappear...")
    time.sleep(2)

    # Try to reconnect
    print("Attempting reconnection...")
    conn.port = None  # Force re-detection
    if conn.connect():
        print("✅ Reconnection successful!")

        # Send test pattern again
        print("Sending test pattern after reconnection...")
        frame = bytes([0xFF, 0xFE, 0xFD] + [0, 255, 0] * 1024)
        if conn.write_frame(frame):
            print("✅ Test pattern sent successfully after replug")

        conn.close()
        return True
    else:
        print("❌ Reconnection failed")
        return False

def main():
    """Run all tests."""
    print("\nTeensy LED Matrix State Management Tests")
    print("=" * 60)

    results = []

    # Run automated tests
    results.append(("Basic Connection", test_basic_connection()))
    results.append(("Mode Switching", test_mode_switching()))
    results.append(("Reconnection", test_reconnection()))
    results.append(("Device Lock", test_device_lock()))

    # Skip manual USB test for automated runs
    # Uncomment to enable manual test:
    # print("\n" + "=" * 60)
    # response = input("Run manual USB unplug/replug test? (y/n): ")
    # if response.lower() == 'y':
    #     results.append(("USB Replug", test_usb_replug_prompt()))

    # Summary
    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{name:30s} {status}")

    passed = sum(1 for _, r in results if r)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")

    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())