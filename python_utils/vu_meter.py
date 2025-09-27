#!/usr/bin/env python3
"""
Horizontal Stereo VU Meter for LED Matrix
-60dB at center, 0dB at left/right edges
"""

import numpy as np
import sounddevice as sd
import time
import argparse
from serial_connection import TeensyConnection
from collections import deque

class StereoVUMeter:
    def __init__(self, width=64, height=16, device=None, sample_rate=44100, palette='classic'):
        self.width = width
        self.height = height
        self.device = device
        self.sample_rate = sample_rate
        self.palette = palette
        
        # VU meter parameters
        self.db_range = 60  # -60dB to 0dB
        self.ref_level = 1.0  # Reference level for 0dB (full scale)
        self.smoothing = 0.5  # Smoothing factor (0-1, higher = more smooth)
        self.gain = 2.0  # Amplification factor (2.0 to boost weak signals)
        
        # Current levels (smoothed)
        self.left_level = -60.0
        self.right_level = -60.0
        
        # Peak hold
        self.left_peak = -60.0
        self.right_peak = -60.0
        self.peak_hold_time = 1.5  # seconds
        self.left_peak_time = 0
        self.right_peak_time = 0
        
        # Frame buffer with double buffering
        self.frame_buffer = np.zeros((height, width, 3), dtype=np.uint8)
        self.prev_left_pos = -1
        self.prev_right_pos = -1
        self.prev_left_peak = -1
        self.prev_right_peak = -1
        
        # Initialize static elements once
        self.static_initialized = False
        
        # Color gradients for VU meter
        self.setup_colors()
        
        # Audio buffer for RMS calculation
        self.buffer_size = int(sample_rate * 0.05)  # 50ms buffer
        self.left_buffer = deque(maxlen=self.buffer_size)
        self.right_buffer = deque(maxlen=self.buffer_size)
        
    def setup_colors(self):
        """Setup color gradient for VU meter based on selected palette"""
        self.left_gradient = []
        self.right_gradient = []
        
        if self.palette == 'classic':
            # Classic Green -> Yellow -> Red for both channels
            # Position 0-31 maps to -60dB to 0dB
            for i in range(32):
                if i < 18:  # Green zone: -60dB to -24dB (positions 0-17)
                    color = (0, 255, 0)
                elif i < 24:  # Green to Yellow transition: -24dB to -12dB (positions 18-23)
                    ratio = (i - 18) / 6.0
                    color = (int(255 * ratio), 255, 0)
                elif i < 28:  # Yellow zone: -12dB to -6dB (positions 24-27)
                    color = (255, 255, 0)
                else:  # Yellow to Red transition: -6dB to 0dB (positions 28-31)
                    ratio = (i - 28) / 3.0
                    green = int(255 * (1 - ratio))
                    color = (255, green, 0)
                self.left_gradient.append(color)
                self.right_gradient.append(color)
                
        elif self.palette == 'split':
            # Red for left, Green for right
            for i in range(32):
                # Left channel - red gradient
                intensity = int(100 + (155 * i / 31))  # From dim to bright
                self.left_gradient.append((intensity, 0, 0))
                # Right channel - green gradient
                self.right_gradient.append((0, intensity, 0))
                
        elif self.palette == 'rainbow':
            # Full rainbow gradient
            for i in range(32):
                hue = i / 31.0  # 0 to 1
                # HSV to RGB conversion (simplified)
                if hue < 1/6:
                    color = (255, int(255 * hue * 6), 0)
                elif hue < 2/6:
                    color = (int(255 * (2 - hue * 6)), 255, 0)
                elif hue < 3/6:
                    color = (0, 255, int(255 * (hue * 6 - 2)))
                elif hue < 4/6:
                    color = (0, int(255 * (4 - hue * 6)), 255)
                elif hue < 5/6:
                    color = (int(255 * (hue * 6 - 4)), 0, 255)
                else:
                    color = (255, 0, int(255 * (6 - hue * 6)))
                self.left_gradient.append(color)
                self.right_gradient.append(color)
                
        elif self.palette == 'viridis':
            # Viridis-like gradient (purple -> blue -> green -> yellow)
            for i in range(32):
                t = i / 31.0
                r = int(255 * (0.267 + 0.733 * t))
                g = int(255 * (0.329 + 0.671 * t))
                b = int(255 * (0.754 * (1 - t)))
                self.left_gradient.append((r, g, b))
                self.right_gradient.append((r, g, b))
                
        elif self.palette == 'fire':
            # Fire gradient (black -> red -> orange -> yellow -> white)
            for i in range(32):
                t = i / 31.0
                if t < 0.25:
                    # Black to red
                    r = int(255 * t * 4)
                    g = 0
                    b = 0
                elif t < 0.5:
                    # Red to orange
                    r = 255
                    g = int(255 * (t - 0.25) * 4)
                    b = 0
                elif t < 0.75:
                    # Orange to yellow
                    r = 255
                    g = 255
                    b = int(255 * (t - 0.5) * 4)
                else:
                    # Yellow to white
                    r = 255
                    g = 255
                    b = 255
                self.left_gradient.append((r, g, b))
                self.right_gradient.append((r, g, b))
                
        elif self.palette == 'ocean':
            # Ocean gradient (dark blue -> cyan -> white)
            for i in range(32):
                t = i / 31.0
                r = int(255 * t * t)
                g = int(255 * (0.3 + 0.7 * t))
                b = int(255 * (0.5 + 0.5 * t))
                self.left_gradient.append((r, g, b))
                self.right_gradient.append((r, g, b))
                
        else:  # Default to classic
            # Fallback to classic palette
            for i in range(32):
                if i < 20:
                    color = (0, 255, 0)
                elif i < 28:
                    ratio = (i - 20) / 8
                    color = (int(255 * ratio), 255, 0)
                else:
                    color = (255, int(255 * (1 - (i - 28) / 4)), 0)
                self.left_gradient.append(color)
                self.right_gradient.append(color)
    
    def db_to_position(self, db_value):
        """Convert dB value to horizontal position (0-31 for each channel)"""
        # Clamp to range (allow slightly above 0 for clipping)
        db_value = max(-60, min(3, db_value))
        # Linear mapping from -60dB to 0dB -> 0 to 31
        # Values above 0dB still map to position 31 (full scale)
        if db_value > 0:
            return 31
        return int((db_value + 60) / 60 * 31)
    
    def amplitude_to_db(self, amplitude):
        """Convert amplitude to dB"""
        if amplitude <= 0:
            return -60.0
        # Allow positive dB for clipping indication
        db = 20 * np.log10(amplitude / self.ref_level)
        # Clamp to range but allow up to +3dB for clipping
        return max(-60.0, min(3.0, db))
    
    def audio_callback(self, indata, frames, time_info, status):
        """Process audio input"""
        if status:
            print(f"Audio status: {status}")
        
        # Handle variable channel counts
        if len(indata.shape) == 1:
            # Mono input (1D array)
            left_channel = indata
            right_channel = indata
        elif indata.shape[1] >= 2:
            # Stereo or multi-channel
            left_channel = indata[:, 0]
            right_channel = indata[:, 1]
        else:
            # Single channel (2D array with 1 channel)
            left_channel = indata[:, 0]
            right_channel = indata[:, 0]
        
        # Add to buffers
        self.left_buffer.extend(left_channel)
        self.right_buffer.extend(right_channel)
        
        # Calculate RMS
        if len(self.left_buffer) > 0:
            left_rms = np.sqrt(np.mean(np.square(list(self.left_buffer))))
            right_rms = np.sqrt(np.mean(np.square(list(self.right_buffer))))
            
            # Apply gain for weak signals
            left_rms *= self.gain
            right_rms *= self.gain
            
            # Convert to dB
            left_db = self.amplitude_to_db(left_rms)
            right_db = self.amplitude_to_db(right_rms)
            
            # Apply smoothing
            self.left_level = (self.smoothing * self.left_level + 
                              (1 - self.smoothing) * left_db)
            self.right_level = (self.smoothing * self.right_level + 
                               (1 - self.smoothing) * right_db)
            
            # Update peaks
            current_time = time.time()
            
            if self.left_level > self.left_peak or (current_time - self.left_peak_time) > self.peak_hold_time:
                self.left_peak = self.left_level
                self.left_peak_time = current_time
            
            if self.right_level > self.right_peak or (current_time - self.right_peak_time) > self.peak_hold_time:
                self.right_peak = self.right_level
                self.right_peak_time = current_time
    
    def render_frame(self):
        """Render VU meter to frame buffer with optimized updates"""
        # Initialize static elements only once
        if not self.static_initialized:
            # Clear once at start
            self.frame_buffer.fill(0)
            
            # Draw static center line (at -60dB)
            for y in range(self.height):
                self.frame_buffer[y, 31] = (40, 40, 40)  # Dim gray
                self.frame_buffer[y, 32] = (40, 40, 40)
            
            # Add static scale markers at top and bottom
            # -60dB (center) markers at top and bottom
            self.frame_buffer[0, 31] = (100, 100, 100)
            self.frame_buffer[0, 32] = (100, 100, 100)
            self.frame_buffer[15, 31] = (100, 100, 100)
            self.frame_buffer[15, 32] = (100, 100, 100)
            
            # -40dB markers at top and bottom
            self.frame_buffer[0, 21] = (80, 80, 80)  # Left
            self.frame_buffer[0, 42] = (80, 80, 80)  # Right
            self.frame_buffer[15, 21] = (80, 80, 80)  # Left
            self.frame_buffer[15, 42] = (80, 80, 80)  # Right
            
            # -20dB markers at top and bottom
            self.frame_buffer[0, 11] = (100, 100, 100)  # Left
            self.frame_buffer[0, 52] = (100, 100, 100)  # Right
            self.frame_buffer[15, 11] = (100, 100, 100)  # Left
            self.frame_buffer[15, 52] = (100, 100, 100)  # Right
            
            # 0dB markers (edges) - full height
            for y in range(self.height):
                self.frame_buffer[y, 0] = (150, 150, 150)  # Left edge
                self.frame_buffer[y, 63] = (150, 150, 150)  # Right edge
            
            self.static_initialized = True
        
        # Get current positions
        left_pos = self.db_to_position(self.left_level)
        right_pos = self.db_to_position(self.right_level)
        left_peak_pos = self.db_to_position(self.left_peak)
        right_peak_pos = self.db_to_position(self.right_peak)
        
        # VU bar vertical range - make it much taller (12 pixels out of 16)
        vu_y_start = 2
        vu_y_end = 14
        
        # Update left channel only if changed
        if left_pos != self.prev_left_pos or left_peak_pos != self.prev_left_peak:
            # Clear previous left channel bar area (not the static elements)
            for y in range(vu_y_start, vu_y_end):
                for x in range(1, 31):  # Skip edge marker at x=0
                    self.frame_buffer[y, x] = (0, 0, 0)
            
            # Draw new left channel bar
            for y in range(vu_y_start, vu_y_end):
                for x in range(left_pos + 1):
                    pos = 31 - x  # Mirror for left side
                    if pos > 0 and pos < 31:  # Skip static markers
                        color = self.left_gradient[x]
                        if x < left_pos:
                            self.frame_buffer[y, pos] = [c // 4 for c in color]  # Dimmed trail
                        elif x == left_pos:
                            self.frame_buffer[y, pos] = color  # Full brightness at current level
                
                # Draw peak indicator
                if left_peak_pos < 31:
                    peak_x = 31 - left_peak_pos
                    if peak_x > 0:  # Don't overwrite edge marker
                        self.frame_buffer[y, peak_x] = (255, 255, 255)  # White peak
            
            self.prev_left_pos = left_pos
            self.prev_left_peak = left_peak_pos
        
        # Update right channel only if changed
        if right_pos != self.prev_right_pos or right_peak_pos != self.prev_right_peak:
            # Clear previous right channel bar area (not the static elements)
            for y in range(vu_y_start, vu_y_end):
                for x in range(33, 63):  # Skip center line and edge marker
                    self.frame_buffer[y, x] = (0, 0, 0)
            
            # Draw new right channel bar
            for y in range(vu_y_start, vu_y_end):
                for x in range(right_pos + 1):
                    pos = 32 + x  # Right side starts at column 32
                    if pos > 32 and pos < 63:  # Skip static markers
                        color = self.right_gradient[x]
                        if x < right_pos:
                            self.frame_buffer[y, pos] = [c // 4 for c in color]  # Dimmed trail
                        elif x == right_pos:
                            self.frame_buffer[y, pos] = color  # Full brightness at current level
                
                # Draw peak indicator
                if right_peak_pos < 31:
                    peak_x = 32 + right_peak_pos
                    if peak_x < 63:  # Don't overwrite edge marker
                        self.frame_buffer[y, peak_x] = (255, 255, 255)  # White peak
            
            self.prev_right_pos = right_pos
            self.prev_right_peak = right_peak_pos
    
    def print_frame(self):
        """Print ASCII representation for testing"""
        print("\033[H\033[J", end='')  # Clear screen
        print("Horizontal Stereo VU Meter")
        print(f"Left: {self.left_level:+.1f}dB (peak: {self.left_peak:+.1f}dB)")
        print(f"Right: {self.right_level:+.1f}dB (peak: {self.right_peak:+.1f}dB)")
        print("-" * 66)
        
        # Simple ASCII visualization
        left_bar = int((self.left_level + 60) / 60 * 30)
        right_bar = int((self.right_level + 60) / 60 * 30)
        
        # Left channel (reversed)
        left_str = ""
        for i in range(30, -1, -1):
            if i == left_bar:
                left_str += "█"
            elif i < left_bar:
                left_str += "▒"
            else:
                left_str += " "
        
        # Right channel
        right_str = ""
        for i in range(31):
            if i == right_bar:
                right_str += "█"
            elif i < right_bar:
                right_str += "▒"
            else:
                right_str += " "
        
        print(f"L: {left_str}|{right_str} :R")
        print("   0dB" + " " * 20 + "-60dB" + " " * 20 + "0dB")
    
    def run(self, ser=None, test_mode=False):
        """Run the VU meter"""
        try:
            # Get device info to determine channel count
            if self.device is not None:
                device_info = sd.query_devices(self.device)
                channels = min(2, device_info['max_input_channels'])
            else:
                channels = 2
            
            # Start audio stream
            with sd.InputStream(device=self.device,
                               channels=channels,
                               samplerate=self.sample_rate,
                               callback=self.audio_callback,
                               blocksize=1024):
                
                print("VU Meter running... Press Ctrl+C to stop")
                
                while True:
                    # Render frame
                    self.render_frame()
                    
                    # Send to LED matrix or print
                    if ser and not test_mode:
                        frame_bytes = b'\xFF\xFE\xFD' + self.frame_buffer.flatten().tobytes()
                        if not ser.write_frame(frame_bytes):
                            print("Write error, retrying...")
                    else:
                        self.print_frame()
                    
                    # Higher frame rate for smoother animation
                    time.sleep(1/60)  # 60 FPS
                    
        except KeyboardInterrupt:
            print("\nStopping VU meter...")

def main():
    parser = argparse.ArgumentParser(description='Horizontal Stereo VU Meter for LED Matrix')
    parser.add_argument('--source', type=str, choices=['mic', 'system', 'auto'], default='auto',
                       help='Audio source: mic (microphone), system (desktop audio), auto (find best)')
    parser.add_argument('--device', type=int, help='Audio input device index (overrides --source)')
    parser.add_argument('--list-devices', action='store_true', help='List available audio devices')
    parser.add_argument('--port', type=str, help='Serial port for Teensy')
    parser.add_argument('--test', action='store_true', help='Run in test mode (no hardware)')
    parser.add_argument('--smoothing', type=float, default=0.5, help='Smoothing factor (0-1)')
    parser.add_argument('--palette', type=str, default='rainbow',
                       choices=['classic', 'split', 'rainbow', 'viridis', 'fire', 'ocean'],
                       help='Color palette: classic (green/yellow/red), split (red left/green right), rainbow, viridis, fire, ocean')
    parser.add_argument('--gain', type=float, default=2.0, help='Input gain multiplier (default: 2.0)')
    parser.add_argument('--brightness', type=float, default=1.0, 
                       help='Brightness level (0.0-1.0, default: 1.0). Use 0.3 for nighttime')
    
    args = parser.parse_args()
    
    if args.list_devices:
        print("Available audio devices:")
        devices = sd.query_devices()
        print("\nAll devices (including outputs that can be monitored):")
        for i, dev in enumerate(devices):
            marker = ""
            name_lower = dev['name'].lower()
            if 'monitor' in name_lower:
                marker = " [MONITOR]"
            elif 'pulse' in name_lower:
                marker = " [PULSE]"
            elif 'mic' in name_lower or 'input' in name_lower or 'capture' in name_lower:
                marker = " [MIC]"
            elif 'qudelix' in name_lower or 't71' in name_lower:
                marker = " [QUDELIX]"
            
            if dev['max_input_channels'] > 0:
                print(f"  {i}: IN  {dev['name']} ({dev['max_input_channels']} ch){marker}")
            elif dev['max_output_channels'] > 0:
                print(f"  {i}: OUT {dev['name']} ({dev['max_output_channels']} ch){marker}")
        
        print("\nTip: Use device index with --device N")
        print("     PulseAudio device (26 or 27) often provides system audio monitoring")
        return
    
    # Auto-detect device based on source preference
    device_id = args.device
    if device_id is None and args.source != 'auto':
        devices = sd.query_devices()
        
        if args.source == 'system':
            # Look for PulseAudio monitor or similar system audio devices
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    name_lower = dev['name'].lower()
                    if 'pulse' in name_lower:
                        device_id = i
                        print(f"Auto-selected PulseAudio: {dev['name']}")
                        print("This will monitor all system audio including Qudelix T71")
                        break
                    elif 'monitor' in name_lower or 'stereo mix' in name_lower or 'what u hear' in name_lower:
                        device_id = i
                        print(f"Auto-selected system audio: {dev['name']}")
                        break
            if device_id is None:
                print("No system audio monitor found. Try --list-devices to see available options.")
                print("You may need to enable stereo mix or install PulseAudio.")
                return
        
        elif args.source == 'mic':
            # Look for microphone devices
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    name_lower = dev['name'].lower()
                    if 'mic' in name_lower or 'input' in name_lower or 'capture' in name_lower:
                        device_id = i
                        print(f"Auto-selected microphone: {dev['name']}")
                        break
            if device_id is None:
                # Fallback to default input device
                device_id = sd.default.device[0]
                if device_id is not None:
                    print(f"Using default input device: {devices[device_id]['name']}")
                else:
                    print("No microphone found. Try --list-devices to see available options.")
                    return
    
    # Create VU meter
    vu = StereoVUMeter(device=device_id, palette=args.palette)
    vu.smoothing = args.smoothing
    vu.gain = args.gain
    
    # Connect to Teensy if not test mode
    ser = None
    if not args.test:
        ser = TeensyConnection(port=args.port, brightness=args.brightness)
        if not ser.connect(mode='s'):
            print("Failed to connect to Teensy!")
            return 1
        print(f"Connected to {ser.port}")
    
    try:
        # Run VU meter
        vu.run(ser, args.test)
    finally:
        if ser:
            ser.close()

if __name__ == "__main__":
    main()