#!/usr/bin/env python3
"""
Robust serial connection handler with auto-detection and retry logic.
"""

import serial
import serial.tools.list_ports
import time
import sys
import os
from typing import Optional, List
try:
    from .device_lock import DeviceLock
except ImportError:
    from device_lock import DeviceLock

class TeensyConnection:
    """Manages serial connection to Teensy with auto-detection and error recovery."""

    def __init__(self, port: Optional[str] = None, baudrate: int = 6000000, timeout: float = 2.0, brightness: float = 0.375):
        """
        Initialize connection handler.

        Args:
            port: Serial port (if None, auto-detect)
            baudrate: Serial baudrate
            timeout: Read/write timeout in seconds
            brightness: Global brightness multiplier (0.0-1.0)
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = None
        self.last_connect_time = 0
        self.connection_attempts = 0
        self.max_retries = 3
        self.brightness = max(0.0, min(1.0, brightness))
        self._device_lock: Optional[DeviceLock] = None

    def find_teensy_ports(self) -> List[str]:
        """Find all available Teensy serial ports."""
        ports = []
        for port in serial.tools.list_ports.comports():
            if 'teensy' in port.description.lower() or \
               'usb serial' in port.description.lower() or \
               port.device.startswith('/dev/ttyACM') or \
               port.device.startswith('/dev/ttyUSB'):
                ports.append(port.device)
        return sorted(ports)

    def connect(self, mode: str = 's', retries: int = None) -> bool:
        """
        Establish connection to Teensy with retries.

        Args:
            mode: Operating mode ('s' for streaming, 'e' for effects)
            retries: Number of connection attempts (if None, use default)

        Returns:
            True if connected successfully
        """
        if retries is None:
            retries = self.max_retries

        # Close existing connection
        if self.ser and self.ser.is_open:
            self.ser.close()
            time.sleep(0.1)

        # Auto-detect port if not specified
        if not self.port:
            ports = self.find_teensy_ports()
            if not ports:
                print("Error: No Teensy found. Please check USB connection.", file=sys.stderr)
                return False
            self.port = ports[0]
            if len(ports) > 1:
                print(f"Multiple ports found: {ports}. Using {self.port}", file=sys.stderr)

        # Acquire device lock first
        try:
            self._device_lock = DeviceLock(self.port, timeout=2.0)
            if not self._device_lock.acquire():
                lock_info = self._device_lock.get_lock_info()
                error_msg = f"Device {self.port} is locked by another process"
                if lock_info:
                    error_msg += f":\n{lock_info}"
                print(f"Error: {error_msg}", file=sys.stderr)
                return False
        except Exception as e:
            print(f"Error acquiring device lock: {e}", file=sys.stderr)
            return False

        # Try to connect with retries
        for attempt in range(retries):
            try:
                print(f"Attempting connection to {self.port} (attempt {attempt + 1}/{retries})...", file=sys.stderr)

                # Open serial connection
                self.ser = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=self.timeout,
                    write_timeout=self.timeout
                )

                # Clear buffers
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                time.sleep(0.1)

                # Send mode command
                self.ser.write(mode.encode())
                self.ser.flush()
                time.sleep(0.5)  # Give Teensy time to switch modes and process command

                print(f"Connected successfully to {self.port}", file=sys.stderr)
                self.last_connect_time = time.time()
                self.connection_attempts = 0
                return True

            except serial.SerialException as e:
                print(f"Connection attempt {attempt + 1} failed: {e}", file=sys.stderr)

                # Try alternative port on failure
                if attempt < retries - 1:
                    time.sleep(0.5)
                    ports = self.find_teensy_ports()
                    if ports and ports[0] != self.port:
                        self.port = ports[0]
                        print(f"Switching to port {self.port}", file=sys.stderr)

            except Exception as e:
                print(f"Unexpected error: {e}", file=sys.stderr)

        return False

    def apply_brightness(self, data: bytes) -> bytes:
        """
        Apply brightness adjustment to frame data.

        Args:
            data: Raw frame data with header

        Returns:
            Frame data with brightness applied
        """
        if self.brightness >= 0.99:  # Skip if essentially full brightness
            return data

        # Keep header intact (first 3 bytes)
        result = bytearray(data[:3])

        # Apply brightness to RGB data
        for i in range(3, len(data)):
            result.append(int(data[i] * self.brightness))

        return bytes(result)

    def write_frame(self, data: bytes, retry_on_error: bool = True, apply_brightness: bool = True) -> bool:
        """
        Write a frame to the Teensy with error recovery.

        Args:
            data: Frame data to write
            retry_on_error: Whether to reconnect and retry on failure
            apply_brightness: Whether to apply brightness adjustment

        Returns:
            True if write successful
        """
        if not self.ser or not self.ser.is_open:
            if not self.connect():
                return False

        try:
            # Apply brightness if requested
            if apply_brightness:
                data = self.apply_brightness(data)

            self.ser.write(data)
            self.ser.flush()
            return True

        except serial.SerialTimeoutException:
            print("Write timeout - buffer may be full", file=sys.stderr)
            if retry_on_error and self.connection_attempts < 3:
                self.connection_attempts += 1
                time.sleep(0.1)
                if self.connect():
                    return self.write_frame(data, retry_on_error=False)
            return False

        except serial.SerialException as e:
            print(f"Serial error: {e}", file=sys.stderr)
            if retry_on_error:
                # Port might have changed
                self.port = None  # Force re-detection
                if self.connect():
                    return self.write_frame(data, retry_on_error=False)
            return False

        except Exception as e:
            print(f"Unexpected write error: {e}", file=sys.stderr)
            return False

    def set_mode(self, mode: str) -> bool:
        """Set device mode."""
        try:
            if not self.ser or not self.ser.is_open:
                return False
            self.ser.write(mode.encode())
            self.ser.flush()
            time.sleep(0.2)
            return True
        except Exception as e:
            print(f"Mode change error: {e}", file=sys.stderr)
            return False

    def close(self):
        """Close the serial connection."""
        # Close basic connection
        if self.ser and self.ser.is_open:
            try:
                # Send effects mode unless told to keep stream mode
                if not os.environ.get('LED_MATRIX_KEEP_STREAM_MODE'):
                    self.ser.write(b'e')
                    self.ser.flush()
                    time.sleep(0.1)
            except:
                pass
            finally:
                self.ser.close()

        # Release device lock
        if self._device_lock:
            try:
                self._device_lock.release()
                self._device_lock = None
            except Exception as e:
                print(f"Error releasing device lock: {e}", file=sys.stderr)

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def test_connection():
    """Test the serial connection."""
    print("Testing Teensy connection...")

    conn = TeensyConnection()
    if conn.connect():
        print("Connection test successful!")

        # Send test pattern
        print("Sending test pattern...")
        for i in range(10):
            frame = bytes([0xFF, 0xFE, 0xFD])
            # Create a simple color pattern
            for y in range(16):
                for x in range(64):
                    frame += bytes([
                        (x * 4) % 256,  # Red gradient
                        (y * 16) % 256,  # Green gradient
                        (i * 25) % 256   # Blue animation
                    ])

            if not conn.write_frame(frame):
                print("Failed to write frame")
                break
            time.sleep(0.05)

        conn.close()
        print("Test complete")
    else:
        print("Connection test failed")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(test_connection())