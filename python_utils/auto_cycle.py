#!/usr/bin/env python3
"""
Auto-cycle through various LED matrix visualizations
Automatically switches between different modes and effects
"""

import subprocess
import time
import random
import signal
import sys
import os
import argparse
from pathlib import Path
import serial
import serial.tools.list_ports

class AutoCycler:
    def __init__(self, device=None, cycle_time=30, random_order=False, modes=None):
        self.device = device
        self.cycle_time = cycle_time
        self.random_order = random_order
        self.current_process = None
        self.running = True
        self.serial_conn = None  # Persistent serial connection
        
        # Get Python command - use venv Python explicitly
        venv_python = Path(__file__).parent.parent / 'venv' / 'bin' / 'python3'
        if venv_python.exists():
            self.python_cmd = str(venv_python)
        else:
            self.python_cmd = str(Path(sys.executable).resolve())
        
        # Define all available presets
        self.all_presets = [
            # VU Meter variations
            {
                'name': 'Classic VU Meter',
                'script': 'vu_meter.py',
                'args': ['--palette', 'classic', '--gain', '3.0']
            },
            {
                'name': 'Rainbow VU Meter',
                'script': 'vu_meter.py',
                'args': ['--palette', 'rainbow', '--gain', '3.0']
            },
            {
                'name': 'Fire VU Meter',
                'script': 'vu_meter.py',
                'args': ['--palette', 'fire', '--gain', '4.0']
            },
            {
                'name': 'Split Channel VU',
                'script': 'vu_meter.py',
                'args': ['--palette', 'split', '--gain', '3.0']
            },
            
            # Spectrogram variations
            {
                'name': 'Vertical Spectrogram',
                'script': 'spectrogram.py',
                'args': ['--mode', 'vertical']
            },
            {
                'name': 'Horizontal Spectrogram',
                'script': 'spectrogram.py',
                'args': ['--mode', 'horizontal']
            },
            
            # Phase meter - Basic
            {
                'name': 'Classic Lissajous',
                'script': 'phase_meter.py',
                'args': ['--mode', 'lissajous', '--color', 'green', '--persistence', '0.85']
            },
            {
                'name': 'Rainbow Lissajous',
                'script': 'phase_meter.py',
                'args': ['--mode', 'lissajous', '--color', 'rainbow', '--persistence', '0.9']
            },
            
            # Phase meter - Rotating
            {
                'name': 'Rotating Rainbow',
                'script': 'phase_meter.py',
                'args': ['--mode', 'lissajous', '--color', 'rainbow', '--rotate', '15', '--persistence', '0.9']
            },
            {
                'name': 'Spinning Cyan',
                'script': 'phase_meter.py',
                'args': ['--mode', 'lissajous', '--color', 'cyan', '--rotate', '25', '--persistence', '0.85']
            },
            
            # Phase meter - Symmetry
            {
                'name': 'Mirror Symmetry',
                'script': 'phase_meter.py',
                'args': ['--mode', 'lissajous', '--symmetry', 'mirror', '--color', 'green', '--rotate', '10']
            },
            {
                'name': 'Quad Symmetry',
                'script': 'phase_meter.py',
                'args': ['--mode', 'lissajous', '--symmetry', 'quad', '--color', 'amber', '--persistence', '0.9']
            },
            {
                'name': 'Kaleidoscope',
                'script': 'phase_meter.py',
                'args': ['--mode', 'lissajous', '--symmetry', 'kaleidoscope', '--color', 'rainbow', '--rotate', '12']
            },
            
            # Phase meter - Trail effects
            {
                'name': 'Rainbow Trails',
                'script': 'phase_meter.py',
                'args': ['--mode', 'lissajous', '--trail', 'rainbow', '--persistence', '0.95', '--rotate', '8']
            },
            {
                'name': 'Decay Trails',
                'script': 'phase_meter.py',
                'args': ['--mode', 'lissajous', '--trail', 'decay', '--persistence', '0.92', '--color', 'white']
            },
            
            # Phase meter - Beat reactive
            {
                'name': 'Beat Reactive',
                'script': 'phase_meter.py',
                'args': ['--mode', 'lissajous', '--beat', '--color', 'cyan', '--rotate', '20']
            },
            {
                'name': 'Beat Kaleidoscope',
                'script': 'phase_meter.py',
                'args': ['--mode', 'lissajous', '--symmetry', 'kaleidoscope', '--beat', '--color', 'rainbow']
            },
            
            # Phase meter - Oscilloscope modes
            {
                'name': 'Vertical Scope',
                'script': 'phase_meter.py',
                'args': ['--mode', 'vertical', '--color', 'green']
            },
            {
                'name': 'Horizontal Scope',
                'script': 'phase_meter.py',
                'args': ['--mode', 'horizontal', '--color', 'cyan']
            },
            
            # Complex combinations
            {
                'name': 'Psychedelic',
                'script': 'phase_meter.py',
                'args': ['--mode', 'lissajous', '--symmetry', 'kaleidoscope', '--trail', 'decay', 
                        '--rotate', '18', '--color', 'rainbow', '--persistence', '0.93', '--beat']
            },
            {
                'name': 'Hypnotic Spiral',
                'script': 'phase_meter.py',
                'args': ['--mode', 'lissajous', '--rotate', '5', '--persistence', '0.98', '--color', 'amber']
            },
            {
                'name': 'Matrix Rain',
                'script': 'phase_meter.py',
                'args': ['--mode', 'lissajous', '--trail', 'decay', '--color', 'green', 
                        '--persistence', '0.88', '--rotate', '30']
            }
        ]
        
        # Filter presets based on modes argument
        if modes:
            mode_list = modes.split(',')
            self.presets = []
            for mode in mode_list:
                mode = mode.strip().lower()
                if mode == 'vu':
                    self.presets.extend([p for p in self.all_presets if 'vu_meter' in p['script']])
                elif mode == 'phase':
                    self.presets.extend([p for p in self.all_presets if 'phase_meter' in p['script']])
                elif mode == 'spec':
                    self.presets.extend([p for p in self.all_presets if 'spectrogram' in p['script']])
                elif mode == 'simple':
                    # Just basic modes without fancy effects
                    self.presets.extend([p for p in self.all_presets 
                                       if 'Classic' in p['name'] or 'Vertical' in p['name']])
                elif mode == 'fancy':
                    # Just the complex/psychedelic modes
                    self.presets.extend([p for p in self.all_presets 
                                       if any(x in p['name'] for x in ['Psychedelic', 'Kaleidoscope', 
                                                                        'Hypnotic', 'Rainbow Trails'])])
        else:
            self.presets = self.all_presets
        
        if not self.presets:
            print("No presets selected!")
            self.presets = self.all_presets
        
        # Shuffle if random
        if self.random_order:
            random.shuffle(self.presets)
        
        self.current_index = 0
    
    def init_serial_connection(self):
        """Initialize persistent serial connection to keep panel in stream mode"""
        try:
            # Find Teensy port
            ports = []
            for port in serial.tools.list_ports.comports():
                if 'teensy' in port.description.lower() or \
                   'usb serial' in port.description.lower() or \
                   port.device.startswith('/dev/ttyACM'):
                    ports.append(port.device)
            
            if not ports:
                print("Warning: No Teensy found for persistent connection", file=sys.stderr)
                return False
            
            port = ports[0]
            print(f"Initializing persistent connection to {port}...", file=sys.stderr)
            
            # Open serial connection
            self.serial_conn = serial.Serial(
                port=port,
                baudrate=6000000,
                timeout=2.0,
                write_timeout=2.0
            )
            
            # Clear buffers
            self.serial_conn.reset_input_buffer()
            self.serial_conn.reset_output_buffer()
            time.sleep(0.1)
            
            # Send streaming mode command
            self.serial_conn.write(b's')
            self.serial_conn.flush()
            time.sleep(0.2)
            
            print("Persistent connection established", file=sys.stderr)
            return True
            
        except Exception as e:
            print(f"Failed to establish persistent connection: {e}", file=sys.stderr)
            self.serial_conn = None
            return False
    
    def keep_alive(self):
        """Send a keep-alive frame to maintain streaming mode"""
        if self.serial_conn and self.serial_conn.is_open:
            try:
                # Send a blank frame to keep connection alive
                frame = bytes([0xFF, 0xFE, 0xFD] + [0] * 3072)
                self.serial_conn.write(frame)
                self.serial_conn.flush()
            except:
                # Connection lost, will reinitialize on next cycle
                self.serial_conn = None
    
    def stop_current(self):
        """Stop the current running process"""
        if self.current_process:
            try:
                # Send SIGINT first (like Ctrl+C) for graceful shutdown
                self.current_process.send_signal(signal.SIGINT)
                time.sleep(1.0)  # Give more time for graceful cleanup
                
                # If still running, terminate
                if self.current_process.poll() is None:
                    self.current_process.terminate()
                    time.sleep(0.5)
                
                # Force kill if still running
                if self.current_process.poll() is None:
                    self.current_process.kill()
                    
                self.current_process = None
            except:
                pass
    
    def run_preset(self, preset):
        """Run a single preset"""
        print(f"\n{'='*60}", flush=True)
        print(f"Starting: {preset['name']}", flush=True)
        print(f"{'='*60}", flush=True)
        
        # Build command
        cmd = [self.python_cmd, f'python_utils/{preset["script"]}']
        cmd.extend(preset['args'])
        
        # Add device if specified
        if self.device is not None:
            cmd.extend(['--device', str(self.device)])
        
        # Set environment variable to tell scripts not to switch modes on exit
        env = os.environ.copy()
        env['LED_MATRIX_KEEP_STREAM_MODE'] = '1'
        
        # Start the process (show errors for debugging)
        self.current_process = subprocess.Popen(cmd, 
                                               stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE,
                                               env=env)
        
        # Show info
        print(f"Running for {self.cycle_time} seconds...", flush=True)
        print(f"Press Ctrl+C to skip to next effect", flush=True)
        print(f"Press Ctrl+C twice quickly to exit", flush=True)
    
    def signal_handler(self, signum, frame):
        """Handle Ctrl+C"""
        print("\nSkipping to next effect...")
        self.stop_current()
    
    def run(self):
        """Main cycle loop"""
        # Set up signal handler
        signal.signal(signal.SIGINT, self.signal_handler)
        
        print(f"\n{'='*60}", flush=True)
        print(f"AUTO-CYCLE MODE", flush=True)
        print(f"{'='*60}", flush=True)
        print(f"Total presets: {len(self.presets)}", flush=True)
        print(f"Cycle time: {self.cycle_time} seconds", flush=True)
        print(f"Order: {'Random' if self.random_order else 'Sequential'}", flush=True)
        print(f"Device: {self.device if self.device else 'Auto'}", flush=True)
        
        # Initialize persistent serial connection
        self.init_serial_connection()
        
        print(f"\nStarting in 3 seconds...", flush=True)
        time.sleep(3)
        
        last_interrupt = 0
        
        try:
            while self.running:
                # Get current preset
                preset = self.presets[self.current_index]
                
                # Run it
                self.run_preset(preset)
                
                # Wait for cycle time or interrupt
                start_time = time.time()
                while (time.time() - start_time) < self.cycle_time:
                    if self.current_process and self.current_process.poll() is not None:
                        # Get error output if process died
                        stdout, stderr = self.current_process.communicate(timeout=0.1)
                        if stderr:
                            print(f"Error: {stderr.decode()[:200]}...")
                        print("Process ended, moving to next...")
                        break
                    time.sleep(0.5)
                
                # Stop current
                self.stop_current()
                
                # Keep serial connection alive between effects
                self.keep_alive()
                
                # Short transition delay (no need for long reset)
                time.sleep(0.5)
                
                # Re-init connection if lost
                if not self.serial_conn or not self.serial_conn.is_open:
                    self.init_serial_connection()
                
                # Move to next
                if self.random_order:
                    self.current_index = random.randint(0, len(self.presets) - 1)
                else:
                    self.current_index = (self.current_index + 1) % len(self.presets)
                
                # Brief pause between effects
                time.sleep(1)
                
        except KeyboardInterrupt:
            # Check for double Ctrl+C
            current_time = time.time()
            if current_time - last_interrupt < 1:
                print("\n\nDouble Ctrl+C detected. Exiting...")
                self.running = False
            else:
                last_interrupt = current_time
                # The signal handler will handle skipping
                
        finally:
            self.stop_current()
            # Close persistent serial connection
            if self.serial_conn and self.serial_conn.is_open:
                try:
                    # Send effects mode before closing
                    self.serial_conn.write(b'e')
                    self.serial_conn.flush()
                    time.sleep(0.1)
                    self.serial_conn.close()
                except:
                    pass
            print("\nAuto-cycle stopped.")

def main():
    parser = argparse.ArgumentParser(description='Auto-cycle through LED matrix effects')
    parser.add_argument('--time', type=int, default=30,
                       help='Time per effect in seconds (default: 30)')
    parser.add_argument('--device', type=int, help='Audio device index')
    parser.add_argument('--random', action='store_true',
                       help='Random order instead of sequential')
    parser.add_argument('--modes', type=str,
                       help='Comma-separated list of modes: vu,phase,spec,simple,fancy')
    
    args = parser.parse_args()
    
    cycler = AutoCycler(
        device=args.device,
        cycle_time=args.time,
        random_order=args.random,
        modes=args.modes
    )
    
    cycler.run()

if __name__ == "__main__":
    main()