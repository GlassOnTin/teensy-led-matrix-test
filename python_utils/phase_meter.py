#!/usr/bin/env python3
"""
Phase Meter / Oscilloscope visualization for LED Matrix
Shows stereo phase relationship as Lissajous patterns or waveforms
"""

import numpy as np
import sounddevice as sd
import time
import argparse
from serial_connection import TeensyConnection
from collections import deque

class PhaseMeter:
    def __init__(self, width=64, height=16, device=None, sample_rate=44100, mode='lissajous'):
        self.width = width
        self.height = height
        self.device = device
        self.sample_rate = sample_rate
        self.mode = mode  # 'lissajous', 'vertical', 'horizontal'
        
        # Audio parameters
        self.gain = 4.0
        self.persistence = 0.85  # Trail persistence (0-1)
        self.brightness = 200  # Max brightness
        
        # Rotation parameters
        self.rotation_speed = 0.0  # Rotation speed in radians per frame
        self.rotation_angle = 0.0  # Current rotation angle
        
        # Creative effect parameters
        self.z_modulation = False  # 3D depth effect
        self.symmetry_mode = 0  # 0=none, 1=mirror, 2=quad, 3=kaleidoscope
        self.trail_mode = 'normal'  # 'normal', 'rainbow_trail', 'decay_color'
        self.beat_reactive = False  # React to beat/bass
        self.frequency_color = False  # Color based on frequency content
        
        # Beat detection
        self.beat_threshold = 0.0
        self.last_beat_time = 0.0
        self.beat_decay = 0.0
        
        # Frequency analysis
        self.freq_bins = None
        
        # Frame buffer with float values for persistence
        self.frame_buffer = np.zeros((height, width, 3), dtype=np.float32)
        self.output_buffer = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Audio buffer for oscilloscope
        self.buffer_size = 512  # Samples to display
        self.left_buffer = deque(maxlen=self.buffer_size)
        self.right_buffer = deque(maxlen=self.buffer_size)
        
        # Color scheme
        self.color_mode = 'green'  # Classic oscilloscope green
        self.setup_colors()
        
    def setup_colors(self):
        """Setup color schemes for different modes"""
        if self.color_mode == 'green':
            # Classic oscilloscope phosphor green
            self.trace_color = np.array([0, 255, 80], dtype=np.float32)
        elif self.color_mode == 'cyan':
            # Digital oscilloscope cyan
            self.trace_color = np.array([0, 200, 255], dtype=np.float32)
        elif self.color_mode == 'amber':
            # Vintage amber
            self.trace_color = np.array([255, 180, 0], dtype=np.float32)
        elif self.color_mode == 'white':
            # Clean white
            self.trace_color = np.array([255, 255, 255], dtype=np.float32)
        elif self.color_mode == 'rainbow':
            # Will be calculated dynamically based on phase
            self.trace_color = None
    
    def audio_callback(self, indata, frames, time_info, status):
        """Process audio input"""
        if status:
            print(f"Audio status: {status}")
        
        # Handle variable channel counts
        if len(indata.shape) == 1:
            # Mono input
            left_channel = indata
            right_channel = indata
        elif indata.shape[1] >= 2:
            # Stereo
            left_channel = indata[:, 0]
            right_channel = indata[:, 1]
        else:
            # Single channel
            left_channel = indata[:, 0]
            right_channel = indata[:, 0]
        
        # Add to buffers
        self.left_buffer.extend(left_channel)
        self.right_buffer.extend(right_channel)
    
    def detect_beat(self, audio_data):
        """Simple beat detection based on energy"""
        energy = np.mean(np.abs(audio_data))
        if energy > self.beat_threshold * 1.5:
            current_time = time.time()
            if current_time - self.last_beat_time > 0.1:  # Min 100ms between beats
                self.last_beat_time = current_time
                self.beat_decay = 1.0
                return True
        # Update threshold with moving average
        self.beat_threshold = self.beat_threshold * 0.95 + energy * 0.05
        return False
    
    def apply_symmetry(self, x, y, color):
        """Apply symmetry transformations"""
        if self.symmetry_mode == 0:  # None
            return [(x, y, color)]
        elif self.symmetry_mode == 1:  # Mirror horizontal
            return [(x, y, color), (self.width - 1 - x, y, color)]
        elif self.symmetry_mode == 2:  # Quad
            return [(x, y, color), 
                    (self.width - 1 - x, y, color),
                    (x, self.height - 1 - y, color),
                    (self.width - 1 - x, self.height - 1 - y, color)]
        elif self.symmetry_mode == 3:  # Kaleidoscope (8-way)
            cx, cy = self.width // 2, self.height // 2
            points = []
            for angle in range(0, 360, 45):
                rad = np.radians(angle)
                cos_a, sin_a = np.cos(rad), np.sin(rad)
                # Rotate around center
                rx = int(cx + (x - cx) * cos_a - (y - cy) * sin_a)
                ry = int(cy + (x - cx) * sin_a + (y - cy) * cos_a)
                if 0 <= rx < self.width and 0 <= ry < self.height:
                    points.append((rx, ry, color))
            return points
        return [(x, y, color)]
    
    def render_lissajous(self):
        """Render Lissajous pattern (X-Y mode)"""
        # Apply persistence decay with trail effects
        if self.trail_mode == 'decay_color':
            # Shift hue as trails decay
            for y in range(self.height):
                for x in range(self.width):
                    if np.max(self.frame_buffer[y, x]) > 10:
                        # Convert to HSV, shift hue, convert back
                        r, g, b = self.frame_buffer[y, x] / 255.0
                        h, s, v = self.rgb_to_hsv(r, g, b)
                        h = (h + 0.01) % 1.0  # Slowly shift hue
                        self.frame_buffer[y, x] = np.array(self.hsv_to_rgb(h, s, v)) * 255 * self.persistence
        else:
            # Normal persistence decay
            self.frame_buffer *= self.persistence
        
        # Beat reactive brightness boost
        if self.beat_reactive and self.beat_decay > 0:
            self.beat_decay *= 0.9
            brightness_boost = 1.0 + self.beat_decay * 0.5
        else:
            brightness_boost = 1.0
        
        if len(self.left_buffer) < 100:
            return
        
        # Get samples
        left_orig = np.array(list(self.left_buffer)) * self.gain
        right_orig = np.array(list(self.right_buffer)) * self.gain
        
        # Limit to reasonable range
        left_orig = np.clip(left_orig, -1, 1)
        right_orig = np.clip(right_orig, -1, 1)
        
        # Keep original for color calculation
        left = left_orig.copy()
        right = right_orig.copy()
        
        # Apply rotation if enabled
        if self.rotation_speed != 0:
            self.rotation_angle += self.rotation_speed
            # Keep angle in range [0, 2π]
            self.rotation_angle = self.rotation_angle % (2 * np.pi)
            
            # Rotate the signal using rotation matrix
            cos_a = np.cos(self.rotation_angle)
            sin_a = np.sin(self.rotation_angle)
            
            # Apply rotation: x' = x*cos - y*sin, y' = x*sin + y*cos
            left = left_orig * cos_a - right_orig * sin_a
            right = left_orig * sin_a + right_orig * cos_a
        
        # Map to display coordinates
        # X axis = left channel, Y axis = right channel
        x_coords = ((left + 1) * (self.width - 1) / 2).astype(int)
        y_coords = ((1 - right) * (self.height - 1) / 2).astype(int)  # Invert Y
        
        # Draw the trace
        for i in range(len(x_coords) - 1):
            x1, y1 = x_coords[i], y_coords[i]
            x2, y2 = x_coords[i + 1], y_coords[i + 1]
            
            # Skip if out of bounds
            if not (0 <= x1 < self.width and 0 <= y1 < self.height):
                continue
            if not (0 <= x2 < self.width and 0 <= y2 < self.height):
                continue
            
            # Calculate color based on phase if rainbow mode
            if self.color_mode == 'rainbow':
                # Calculate the original phase angle before rotation
                original_phase = np.arctan2(right_orig[i], left_orig[i])
                # The color should rotate with the pattern
                # So we subtract the rotation angle to counter the screen-space effect
                color_phase = original_phase - self.rotation_angle
                hue = (color_phase + np.pi) / (2 * np.pi)  # 0 to 1
                hue = hue % 1.0  # Keep in range 0-1
                color = self.hsv_to_rgb(hue, 1.0, 1.0) * self.brightness
            else:
                color = self.trace_color * (self.brightness / 255.0)
            
            # Intensity based on signal strength
            intensity = min(1.0, np.sqrt(left[i]**2 + right[i]**2))
            
            # Draw line segment (simple version)
            # Could use Bresenham's algorithm for better lines
            if abs(x2 - x1) > abs(y2 - y1):
                # More horizontal
                if x1 > x2:
                    x1, x2 = x2, x1
                    y1, y2 = y2, y1
                for x in range(x1, min(x2 + 1, self.width)):
                    t = (x - x1) / max(1, x2 - x1)
                    y = int(y1 + t * (y2 - y1))
                    if 0 <= y < self.height:
                        self.frame_buffer[y, x] = np.maximum(
                            self.frame_buffer[y, x],
                            color * intensity
                        )
            else:
                # More vertical
                if y1 > y2:
                    x1, x2 = x2, x1
                    y1, y2 = y2, y1
                for y in range(y1, min(y2 + 1, self.height)):
                    t = (y - y1) / max(1, y2 - y1)
                    x = int(x1 + t * (x2 - x1))
                    if 0 <= x < self.width:
                        self.frame_buffer[y, x] = np.maximum(
                            self.frame_buffer[y, x],
                            color * intensity
                        )
    
    def render_vertical_scope(self):
        """Render vertical oscilloscope (waveform top to bottom)"""
        # Apply persistence decay
        self.frame_buffer *= self.persistence
        
        if len(self.left_buffer) < self.width:
            return
        
        # Get samples for display width
        left = np.array(list(self.left_buffer))[-self.width:] * self.gain
        right = np.array(list(self.right_buffer))[-self.width:] * self.gain
        
        # Limit to reasonable range
        left = np.clip(left, -1, 1)
        right = np.clip(right, -1, 1)
        
        for x in range(self.width):
            # Left channel (upper half)
            y_left = int((1 - left[x]) * (self.height // 2 - 1))
            if 0 <= y_left < self.height // 2:
                self.frame_buffer[y_left, x] = self.trace_color * (self.brightness / 255.0)
                # Add glow
                if y_left > 0:
                    self.frame_buffer[y_left - 1, x] = np.maximum(
                        self.frame_buffer[y_left - 1, x],
                        self.trace_color * (self.brightness / 510.0)
                    )
                if y_left < self.height // 2 - 1:
                    self.frame_buffer[y_left + 1, x] = np.maximum(
                        self.frame_buffer[y_left + 1, x],
                        self.trace_color * (self.brightness / 510.0)
                    )
            
            # Right channel (lower half)
            y_right = int((1 - right[x]) * (self.height // 2 - 1)) + self.height // 2
            if self.height // 2 <= y_right < self.height:
                self.frame_buffer[y_right, x] = self.trace_color * (self.brightness / 255.0)
                # Add glow
                if y_right > self.height // 2:
                    self.frame_buffer[y_right - 1, x] = np.maximum(
                        self.frame_buffer[y_right - 1, x],
                        self.trace_color * (self.brightness / 510.0)
                    )
                if y_right < self.height - 1:
                    self.frame_buffer[y_right + 1, x] = np.maximum(
                        self.frame_buffer[y_right + 1, x],
                        self.trace_color * (self.brightness / 510.0)
                    )
        
        # Draw center divider
        for x in range(self.width):
            self.frame_buffer[self.height // 2, x] = np.array([40, 40, 40], dtype=np.float32)
    
    def render_horizontal_scope(self):
        """Render horizontal oscilloscope (waveform left to right)"""
        # Apply persistence decay
        self.frame_buffer *= self.persistence
        
        if len(self.left_buffer) < self.height * 2:
            return
        
        # Get samples for display height (stretched)
        samples_needed = self.height * 4
        left = np.array(list(self.left_buffer))[-samples_needed:] * self.gain
        right = np.array(list(self.right_buffer))[-samples_needed:] * self.gain
        
        # Resample to match height
        left = np.interp(np.linspace(0, len(left)-1, self.height), 
                        np.arange(len(left)), left)
        right = np.interp(np.linspace(0, len(right)-1, self.height), 
                         np.arange(len(right)), right)
        
        # Limit to reasonable range
        left = np.clip(left, -1, 1)
        right = np.clip(right, -1, 1)
        
        for y in range(self.height):
            # Left channel (left half)
            x_left = int((left[y] + 1) * (self.width // 2 - 1) / 2)
            if 0 <= x_left < self.width // 2:
                self.frame_buffer[y, x_left] = self.trace_color * (self.brightness / 255.0)
                # Add glow
                if x_left > 0:
                    self.frame_buffer[y, x_left - 1] = np.maximum(
                        self.frame_buffer[y, x_left - 1],
                        self.trace_color * (self.brightness / 510.0)
                    )
                if x_left < self.width // 2 - 1:
                    self.frame_buffer[y, x_left + 1] = np.maximum(
                        self.frame_buffer[y, x_left + 1],
                        self.trace_color * (self.brightness / 510.0)
                    )
            
            # Right channel (right half)
            x_right = int((right[y] + 1) * (self.width // 2 - 1) / 2) + self.width // 2
            if self.width // 2 <= x_right < self.width:
                self.frame_buffer[y, x_right] = self.trace_color * (self.brightness / 255.0)
                # Add glow
                if x_right > self.width // 2:
                    self.frame_buffer[y, x_right - 1] = np.maximum(
                        self.frame_buffer[y, x_right - 1],
                        self.trace_color * (self.brightness / 510.0)
                    )
                if x_right < self.width - 1:
                    self.frame_buffer[y, x_right + 1] = np.maximum(
                        self.frame_buffer[y, x_right + 1],
                        self.trace_color * (self.brightness / 510.0)
                    )
        
        # Draw center divider
        for y in range(self.height):
            self.frame_buffer[y, self.width // 2] = np.array([40, 40, 40], dtype=np.float32)
    
    def hsv_to_rgb(self, h, s, v):
        """Convert HSV to RGB"""
        h = h * 6.0
        i = int(h)
        f = h - i
        p = v * (1 - s)
        q = v * (1 - s * f)
        t = v * (1 - s * (1 - f))
        
        i = i % 6
        if i == 0:
            return np.array([v, t, p])
        elif i == 1:
            return np.array([q, v, p])
        elif i == 2:
            return np.array([p, v, t])
        elif i == 3:
            return np.array([p, q, v])
        elif i == 4:
            return np.array([t, p, v])
        else:
            return np.array([v, p, q])
    
    def rgb_to_hsv(self, r, g, b):
        """Convert RGB to HSV"""
        max_c = max(r, g, b)
        min_c = min(r, g, b)
        delta = max_c - min_c
        
        # Value
        v = max_c
        
        # Saturation
        if max_c != 0:
            s = delta / max_c
        else:
            return 0, 0, 0
        
        # Hue
        if delta == 0:
            h = 0
        elif max_c == r:
            h = ((g - b) / delta) % 6
        elif max_c == g:
            h = (b - r) / delta + 2
        else:
            h = (r - g) / delta + 4
        
        h = h / 6.0
        return h, s, v
    
    def render_frame(self):
        """Render the appropriate visualization"""
        if self.mode == 'lissajous':
            self.render_lissajous()
        elif self.mode == 'vertical':
            self.render_vertical_scope()
        elif self.mode == 'horizontal':
            self.render_horizontal_scope()
        
        # Convert float buffer to uint8 for output
        self.output_buffer = np.clip(self.frame_buffer, 0, 255).astype(np.uint8)
    
    def run(self, ser=None, test_mode=False):
        """Run the phase meter"""
        try:
            # Get device info
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
                               blocksize=256):
                
                print(f"Phase meter running in {self.mode} mode... Press Ctrl+C to stop")
                
                while True:
                    # Render frame
                    self.render_frame()
                    
                    # Send to LED matrix or print
                    if ser and not test_mode:
                        frame_bytes = b'\xFF\xFE\xFD' + self.output_buffer.flatten().tobytes()
                        if not ser.write_frame(frame_bytes):
                            print("Write error, retrying...")
                    elif test_mode:
                        self.print_frame()
                    
                    # Frame rate control
                    time.sleep(1/60)  # 60 FPS for smooth motion
                    
        except KeyboardInterrupt:
            print("\nStopping phase meter...")
    
    def print_frame(self):
        """Print ASCII representation for testing"""
        print("\033[H\033[J", end='')  # Clear screen
        print(f"Phase Meter - {self.mode.capitalize()} Mode")
        print("-" * 66)
        
        # Simple ASCII visualization
        for y in range(self.height):
            line = ""
            for x in range(self.width):
                brightness = np.max(self.output_buffer[y, x])
                if brightness > 200:
                    line += "█"
                elif brightness > 150:
                    line += "▓"
                elif brightness > 100:
                    line += "▒"
                elif brightness > 50:
                    line += "░"
                else:
                    line += " "
            print(line)

def main():
    parser = argparse.ArgumentParser(description='Phase meter / oscilloscope for LED Matrix')
    parser.add_argument('--mode', type=str, choices=['lissajous', 'vertical', 'horizontal'],
                       default='lissajous', help='Display mode')
    parser.add_argument('--source', type=str, choices=['mic', 'system', 'auto'], default='auto',
                       help='Audio source')
    parser.add_argument('--device', type=int, help='Audio input device index')
    parser.add_argument('--list-devices', action='store_true', help='List available audio devices')
    parser.add_argument('--port', type=str, help='Serial port for Teensy')
    parser.add_argument('--test', action='store_true', help='Run in test mode (no hardware)')
    parser.add_argument('--gain', type=float, default=4.0, help='Input gain (default: 4.0)')
    parser.add_argument('--persistence', type=float, default=0.85, 
                       help='Trail persistence 0-1 (default: 0.85)')
    parser.add_argument('--color', type=str, choices=['green', 'cyan', 'amber', 'white', 'rainbow'],
                       default='green', help='Trace color')
    parser.add_argument('--rotate', type=float, default=0.0,
                       help='Rotation speed in degrees/second (default: 0, try 10-30 for slow rotation)')
    parser.add_argument('--symmetry', type=str, choices=['none', 'mirror', 'quad', 'kaleidoscope'],
                       default='none', help='Symmetry mode for patterns')
    parser.add_argument('--trail', type=str, choices=['normal', 'rainbow', 'decay'],
                       default='normal', help='Trail effect mode')
    parser.add_argument('--beat', action='store_true', help='Enable beat-reactive brightness')
    parser.add_argument('--brightness', type=float, default=1.0,
                       help='Brightness level (0.0-1.0, default: 1.0). Use 0.3 for nighttime')
    
    args = parser.parse_args()
    
    if args.list_devices:
        print("Available audio devices:")
        devices = sd.query_devices()
        for i, dev in enumerate(devices):
            if dev['max_input_channels'] > 0:
                print(f"  {i}: {dev['name']} ({dev['max_input_channels']} ch)")
        return
    
    # Auto-detect device based on source
    device_id = args.device
    if device_id is None and args.source != 'auto':
        devices = sd.query_devices()
        
        if args.source == 'system':
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    name_lower = dev['name'].lower()
                    if 'pulse' in name_lower or 'monitor' in name_lower:
                        device_id = i
                        print(f"Auto-selected: {dev['name']}")
                        break
        
        elif args.source == 'mic':
            for i, dev in enumerate(devices):
                if dev['max_input_channels'] > 0:
                    name_lower = dev['name'].lower()
                    if 'mic' in name_lower or 'input' in name_lower:
                        device_id = i
                        print(f"Auto-selected: {dev['name']}")
                        break
    
    # Create phase meter
    phase = PhaseMeter(device=device_id, mode=args.mode)
    phase.gain = args.gain
    phase.persistence = args.persistence
    phase.color_mode = args.color
    phase.setup_colors()
    
    # Set rotation speed (convert degrees/sec to radians/frame at 60 FPS)
    if args.rotate != 0:
        phase.rotation_speed = (args.rotate * np.pi / 180) / 60  # Convert to radians per frame
    
    # Set creative effects
    if args.symmetry == 'mirror':
        phase.symmetry_mode = 1
    elif args.symmetry == 'quad':
        phase.symmetry_mode = 2
    elif args.symmetry == 'kaleidoscope':
        phase.symmetry_mode = 3
    
    if args.trail == 'rainbow':
        phase.trail_mode = 'rainbow_trail'
    elif args.trail == 'decay':
        phase.trail_mode = 'decay_color'
    
    phase.beat_reactive = args.beat
    
    # Connect to Teensy if not test mode
    ser = None
    if not args.test:
        ser = TeensyConnection(port=args.port, brightness=args.brightness)
        if not ser.connect(mode='s'):
            print("Failed to connect to Teensy!")
            return 1
        print(f"Connected to {ser.port}")
    
    try:
        # Run phase meter
        phase.run(ser, args.test)
    finally:
        if ser:
            ser.close()

if __name__ == "__main__":
    main()