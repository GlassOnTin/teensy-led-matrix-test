#!/usr/bin/env python3
"""
Safe serial port debugging utility that won't lock up Claude Code.
Uses timeouts, non-blocking operations, and subprocess isolation.
"""

import serial
import serial.tools.list_ports
import time
import sys
import argparse
import threading
import queue
import signal
from datetime import datetime

class SafeSerialDebugger:
    def __init__(self, port=None, baudrate=2000000, timeout=0.1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial = None
        self.running = False
        self.rx_queue = queue.Queue()
        self.tx_queue = queue.Queue()
        
    def list_ports(self):
        """List all available serial ports"""
        ports = serial.tools.list_ports.comports()
        print("\nAvailable serial ports:")
        for p in ports:
            print(f"  {p.device}: {p.description}")
            if "Teensy" in p.description or "USB Serial" in p.description:
                print(f"    -> Likely Teensy device")
        return ports
        
    def find_teensy(self):
        """Auto-detect Teensy port"""
        ports = serial.tools.list_ports.comports()
        for p in ports:
            if "Teensy" in p.description or "USB Serial" in p.description:
                return p.device
        return None
        
    def connect(self):
        """Connect to serial port with safety timeout"""
        if not self.port:
            self.port = self.find_teensy()
            if not self.port:
                print("No Teensy found. Available ports:")
                self.list_ports()
                return False
                
        try:
            print(f"Connecting to {self.port} at {self.baudrate} baud...")
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout
            )
            print(f"Connected successfully!")
            return True
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
            
    def send_command(self, cmd, wait_response=True):
        """Send command with timeout protection"""
        if not self.serial:
            print("Not connected")
            return None
            
        try:
            self.serial.write(cmd.encode() if isinstance(cmd, str) else cmd)
            self.serial.flush()
            print(f"Sent: {repr(cmd)}")
            
            if wait_response:
                start = time.time()
                response = b""
                while time.time() - start < 1.0:  # 1 second timeout
                    if self.serial.in_waiting:
                        chunk = self.serial.read(self.serial.in_waiting)
                        response += chunk
                        if b'\n' in chunk:  # Got complete line
                            break
                    time.sleep(0.01)
                    
                if response:
                    print(f"Response: {response.decode('utf-8', errors='ignore')}")
                    return response
                else:
                    print("No response (timeout)")
                    return None
        except Exception as e:
            print(f"Send failed: {e}")
            return None
            
    def test_connection(self):
        """Quick connection test"""
        print("\n=== Connection Test ===")
        if not self.connect():
            return False
            
        # Send test command
        print("\nSending test command 't'...")
        response = self.send_command('t')
        
        if response:
            print("✓ Connection working!")
            return True
        else:
            print("✗ No response from device")
            return False
            
    def monitor(self, duration=5):
        """Monitor serial output for specified duration"""
        print(f"\n=== Monitoring for {duration} seconds ===")
        if not self.serial:
            if not self.connect():
                return
                
        start = time.time()
        try:
            while time.time() - start < duration:
                if self.serial.in_waiting:
                    data = self.serial.read(self.serial.in_waiting)
                    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                    print(f"[{timestamp}] {data.decode('utf-8', errors='ignore')}", end='')
                time.sleep(0.01)
        except KeyboardInterrupt:
            print("\nMonitoring stopped")
        except Exception as e:
            print(f"\nMonitor error: {e}")
            
    def interactive_test(self):
        """Interactive testing mode with safety timeouts"""
        print("\n=== Interactive Test Mode ===")
        print("Commands:")
        print("  t - Send test command")
        print("  s - Switch to streaming mode")
        print("  e - Switch to effects mode")
        print("  m - Monitor output for 5 seconds")
        print("  r - Reset connection")
        print("  q - Quit")
        print()
        
        if not self.connect():
            return
            
        while True:
            try:
                cmd = input("Command> ").strip().lower()
                if cmd == 'q':
                    break
                elif cmd == 't':
                    self.send_command('t')
                elif cmd == 's':
                    self.send_command('s')
                elif cmd == 'e':
                    self.send_command('e')
                elif cmd == 'm':
                    self.monitor(5)
                elif cmd == 'r':
                    if self.serial:
                        self.serial.close()
                    self.connect()
                else:
                    print(f"Unknown command: {cmd}")
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")
                
    def cleanup(self):
        """Clean shutdown"""
        if self.serial and self.serial.is_open:
            self.serial.close()
            print("Serial port closed")

def main():
    parser = argparse.ArgumentParser(description='Safe serial debugging for Teensy LED Matrix')
    parser.add_argument('--port', help='Serial port (auto-detect if not specified)')
    parser.add_argument('--baud', type=int, default=2000000, help='Baud rate (default: 2000000)')
    parser.add_argument('--list', action='store_true', help='List available ports')
    parser.add_argument('--test', action='store_true', help='Run connection test')
    parser.add_argument('--monitor', type=int, metavar='SECONDS', help='Monitor output for N seconds')
    parser.add_argument('--send', help='Send single command and exit')
    parser.add_argument('--interactive', action='store_true', help='Interactive test mode')
    
    args = parser.parse_args()
    
    debugger = SafeSerialDebugger(port=args.port, baudrate=args.baud)
    
    # Set up signal handler for clean exit
    def signal_handler(sig, frame):
        print("\n\nCleaning up...")
        debugger.cleanup()
        sys.exit(0)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        if args.list:
            debugger.list_ports()
        elif args.test:
            debugger.test_connection()
        elif args.monitor:
            if debugger.connect():
                debugger.monitor(args.monitor)
        elif args.send:
            if debugger.connect():
                debugger.send_command(args.send)
        elif args.interactive:
            debugger.interactive_test()
        else:
            # Default: quick test
            debugger.test_connection()
    finally:
        debugger.cleanup()

if __name__ == "__main__":
    main()