#!/usr/bin/env python3
"""Capture and visualize what's currently being displayed on the LED matrix"""

import sys
import numpy as np
import time
import argparse
from datetime import datetime
import os

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("ERROR: Pillow not installed. Install with: pip install Pillow")
    sys.exit(1)

class LEDScreenshot:
    """Capture and visualize LED matrix display data"""
    
    def __init__(self, width=64, height=16):
        self.width = width
        self.height = height
        self.frame_buffer = np.zeros((height, width, 3), dtype=np.uint8)
        self.capture_count = 0
        
    def capture_from_stream(self, frame_data):
        """Capture frame data from the stream"""
        if isinstance(frame_data, bytes):
            # Convert bytes to numpy array
            flat_array = np.frombuffer(frame_data, dtype=np.uint8)
            if len(flat_array) == self.width * self.height * 3:
                self.frame_buffer = flat_array.reshape(self.height, self.width, 3)
        else:
            # Assume it's already a numpy array
            self.frame_buffer = frame_data.copy()
        
        self.capture_count += 1
        return self.frame_buffer
    
    def to_image(self, scale=10, show_grid=True):
        """Convert frame buffer to PIL image with optional grid"""
        # Create scaled image
        img_width = self.width * scale
        img_height = self.height * scale
        
        # Create image
        img = Image.new('RGB', (img_width, img_height), color='black')
        draw = ImageDraw.Draw(img)
        
        # Draw pixels
        for y in range(self.height):
            for x in range(self.width):
                r, g, b = self.frame_buffer[y, x]
                color = (int(r), int(g), int(b))
                
                # Draw scaled pixel
                x1 = x * scale
                y1 = y * scale
                x2 = x1 + scale - 1
                y2 = y1 + scale - 1
                
                draw.rectangle([x1, y1, x2, y2], fill=color)
        
        # Draw grid if requested
        if show_grid and scale > 4:
            # Vertical lines
            for x in range(self.width + 1):
                draw.line([(x * scale, 0), (x * scale, img_height)], 
                         fill=(50, 50, 50), width=1)
            
            # Horizontal lines
            for y in range(self.height + 1):
                draw.line([(0, y * scale), (img_width, y * scale)], 
                         fill=(50, 50, 50), width=1)
        
        return img
    
    def to_ascii(self, colored=True):
        """Convert frame buffer to ASCII art representation"""
        # ASCII characters for different brightness levels
        chars = ' .:-=+*#%@'
        
        output = []
        output.append("┌" + "─" * (self.width * 2) + "┐")
        
        for y in range(self.height):
            row = "│"
            for x in range(self.width):
                r, g, b = self.frame_buffer[y, x]
                brightness = (r + g + b) / (3 * 255)
                char_idx = int(brightness * (len(chars) - 1))
                char = chars[char_idx]
                
                if colored and (r > 50 or g > 50 or b > 50):
                    # Use ANSI color codes
                    if r > g and r > b:
                        # Red dominant
                        row += f"\033[91m{char*2}\033[0m"
                    elif g > r and g > b:
                        # Green dominant
                        row += f"\033[92m{char*2}\033[0m"
                    elif b > r and b > g:
                        # Blue dominant
                        row += f"\033[94m{char*2}\033[0m"
                    elif r > 50 and g > 50:
                        # Yellow
                        row += f"\033[93m{char*2}\033[0m"
                    elif g > 50 and b > 50:
                        # Cyan
                        row += f"\033[96m{char*2}\033[0m"
                    elif r > 50 and b > 50:
                        # Magenta
                        row += f"\033[95m{char*2}\033[0m"
                    else:
                        # White
                        row += f"\033[97m{char*2}\033[0m"
                else:
                    row += char * 2
            
            row += "│"
            output.append(row)
        
        output.append("└" + "─" * (self.width * 2) + "┘")
        return "\n".join(output)
    
    def save_image(self, filename=None, scale=10):
        """Save current frame as image"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"led_screenshot_{timestamp}.png"
        
        img = self.to_image(scale=scale)
        img.save(filename)
        return filename
    
    def analyze_content(self):
        """Analyze the current frame content"""
        analysis = {}
        
        # Calculate average brightness
        brightness = np.mean(self.frame_buffer) / 255.0
        analysis['brightness'] = brightness
        
        # Calculate color distribution
        r_mean = np.mean(self.frame_buffer[:, :, 0]) / 255.0
        g_mean = np.mean(self.frame_buffer[:, :, 1]) / 255.0
        b_mean = np.mean(self.frame_buffer[:, :, 2]) / 255.0
        analysis['color_balance'] = {'r': r_mean, 'g': g_mean, 'b': b_mean}
        
        # Find active regions
        threshold = 20
        active_pixels = np.sum(np.any(self.frame_buffer > threshold, axis=2))
        analysis['active_pixels'] = active_pixels
        analysis['active_percentage'] = (active_pixels / (self.width * self.height)) * 100
        
        # Detect patterns
        # Check for vertical bars (spectrogram frequency bands)
        vertical_activity = np.mean(self.frame_buffer, axis=0)
        vertical_variance = np.var(np.max(vertical_activity, axis=1))
        
        # Check for horizontal bars (spectrogram time)
        horizontal_activity = np.mean(self.frame_buffer, axis=1)
        horizontal_variance = np.var(np.max(horizontal_activity, axis=1))
        
        if vertical_variance > horizontal_variance * 2:
            analysis['pattern'] = 'vertical_dominant'
        elif horizontal_variance > vertical_variance * 2:
            analysis['pattern'] = 'horizontal_dominant'
        else:
            analysis['pattern'] = 'mixed'
        
        # Frequency spectrum analysis (for spectrogram)
        # Bottom rows = low freq, top rows = high freq
        low_freq_activity = np.mean(self.frame_buffer[12:16, :])  # Bottom 4 rows
        mid_freq_activity = np.mean(self.frame_buffer[6:10, :])   # Middle rows
        high_freq_activity = np.mean(self.frame_buffer[0:4, :])   # Top 4 rows
        
        analysis['frequency_distribution'] = {
            'low': low_freq_activity / 255.0,
            'mid': mid_freq_activity / 255.0,
            'high': high_freq_activity / 255.0
        }
        
        return analysis


def monitor_spectrogram(duration=10, update_interval=0.5):
    """Monitor the spectrogram display in real-time"""
    import serial
    import serial.tools.list_ports
    
    # Find Teensy
    def find_teensy():
        ports = serial.tools.list_ports.comports()
        for p in ports:
            if any(x in p.description for x in ['Teensy', 'USB Serial', 'ACM']):
                return p.device
        return None
    
    port = find_teensy()
    if not port:
        print("No Teensy found for monitoring")
        return
    
    print(f"Monitoring LED display on {port}")
    print("This will capture what's being sent to the display")
    print("-" * 60)
    
    screenshot = LEDScreenshot()
    
    # We'll intercept the data stream
    # Note: This is a simplified monitor - in production you'd want to
    # properly intercept or mirror the actual data being sent
    
    start_time = time.time()
    last_update = start_time
    
    try:
        while (time.time() - start_time) < duration:
            current_time = time.time()
            
            if current_time - last_update >= update_interval:
                # Clear screen and show current state
                os.system('clear' if os.name == 'posix' else 'cls')
                
                print("LED MATRIX MONITOR")
                print("=" * 60)
                
                # Show ASCII representation
                print(screenshot.to_ascii(colored=True))
                
                # Show analysis
                analysis = screenshot.analyze_content()
                print("\nANALYSIS:")
                print(f"  Brightness: {analysis['brightness']*100:.1f}%")
                print(f"  Active pixels: {analysis['active_pixels']}/{screenshot.width * screenshot.height} ({analysis['active_percentage']:.1f}%)")
                print(f"  Pattern: {analysis['pattern']}")
                print(f"  Color balance: R:{analysis['color_balance']['r']*100:.0f}% G:{analysis['color_balance']['g']*100:.0f}% B:{analysis['color_balance']['b']*100:.0f}%")
                
                if analysis['frequency_distribution']['low'] > 0.01:
                    print(f"  Frequency activity:")
                    print(f"    Low:  {'█' * int(analysis['frequency_distribution']['low'] * 20)}")
                    print(f"    Mid:  {'█' * int(analysis['frequency_distribution']['mid'] * 20)}")
                    print(f"    High: {'█' * int(analysis['frequency_distribution']['high'] * 20)}")
                
                print(f"\nTime: {current_time - start_time:.1f}s / {duration}s")
                print("Press Ctrl+C to stop")
                
                last_update = current_time
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n\nMonitoring stopped")
    
    # Save final screenshot
    filename = screenshot.save_image()
    print(f"Final frame saved to: {filename}")


def main():
    parser = argparse.ArgumentParser(description='LED Matrix Screenshot Tool')
    parser.add_argument('--monitor', action='store_true',
                       help='Monitor display in real-time')
    parser.add_argument('--duration', type=float, default=10,
                       help='Monitoring duration in seconds')
    parser.add_argument('--save', help='Save screenshot to file')
    parser.add_argument('--scale', type=int, default=10,
                       help='Image scale factor (default: 10)')
    
    args = parser.parse_args()
    
    if args.monitor:
        monitor_spectrogram(args.duration)
    else:
        # Single screenshot mode
        screenshot = LEDScreenshot()
        
        # Generate a test pattern for demonstration
        print("Generating test pattern for demonstration...")
        test_frame = np.zeros((16, 64, 3), dtype=np.uint8)
        
        # Create a gradient
        for x in range(64):
            intensity = int((x / 64) * 255)
            for y in range(16):
                if y < 5:
                    test_frame[y, x] = [intensity, 0, 0]  # Red
                elif y < 10:
                    test_frame[y, x] = [0, intensity, 0]  # Green
                else:
                    test_frame[y, x] = [0, 0, intensity]  # Blue
        
        screenshot.capture_from_stream(test_frame)
        
        # Show ASCII
        print("\nASCII representation:")
        print(screenshot.to_ascii(colored=True))
        
        # Show analysis
        analysis = screenshot.analyze_content()
        print("\nFrame Analysis:")
        for key, value in analysis.items():
            if isinstance(value, dict):
                print(f"  {key}:")
                for k, v in value.items():
                    if isinstance(v, float):
                        print(f"    {k}: {v:.2f}")
                    else:
                        print(f"    {k}: {v}")
            elif isinstance(value, float):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")
        
        # Save if requested
        if args.save:
            filename = screenshot.save_image(args.save, scale=args.scale)
            print(f"\nImage saved to: {filename}")


if __name__ == '__main__':
    main()