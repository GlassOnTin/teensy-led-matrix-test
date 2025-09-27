#!/usr/bin/env python3
"""Scrolling text display for LED matrix with colorful effects"""

import sys
import numpy as np
from serial_connection import TeensyConnection
import time
import argparse
from typing import Tuple, Optional, List
import json
import os

class TextScroller:
    """Scrolling text renderer for LED matrix"""
    
    def __init__(self, width=64, height=16):
        self.width = width
        self.height = height
        self.frame_buffer = np.zeros((height, width, 3), dtype=np.uint8)
        
        # Load font data
        self.font = self._load_font()
        self.char_width = 6  # 5 pixels + 1 space
        self.char_height = 8
        
        # Scrolling parameters
        self.scroll_speed = 30  # pixels per second
        self.scroll_position = self.width  # Start off-screen to the right
        
        # Color effects
        self.color_mode = 'rainbow'
        self.color_phase = 0
        
    def _load_font(self):
        """Load or create a simple 5x8 pixel font"""
        # Basic 5x8 font for ASCII characters
        # Each character is represented as 8 bytes (one per row)
        font = {}
        
        # Numbers
        font['0'] = [0x3E, 0x51, 0x49, 0x45, 0x3E, 0x00, 0x00, 0x00]
        font['1'] = [0x00, 0x42, 0x7F, 0x40, 0x00, 0x00, 0x00, 0x00]
        font['2'] = [0x42, 0x61, 0x51, 0x49, 0x46, 0x00, 0x00, 0x00]
        font['3'] = [0x21, 0x41, 0x45, 0x4B, 0x31, 0x00, 0x00, 0x00]
        font['4'] = [0x18, 0x14, 0x12, 0x7F, 0x10, 0x00, 0x00, 0x00]
        font['5'] = [0x27, 0x45, 0x45, 0x45, 0x39, 0x00, 0x00, 0x00]
        font['6'] = [0x3C, 0x4A, 0x49, 0x49, 0x30, 0x00, 0x00, 0x00]
        font['7'] = [0x01, 0x71, 0x09, 0x05, 0x03, 0x00, 0x00, 0x00]
        font['8'] = [0x36, 0x49, 0x49, 0x49, 0x36, 0x00, 0x00, 0x00]
        font['9'] = [0x06, 0x49, 0x49, 0x29, 0x1E, 0x00, 0x00, 0x00]
        
        # Uppercase letters
        font['A'] = [0x7E, 0x11, 0x11, 0x11, 0x7E, 0x00, 0x00, 0x00]
        font['B'] = [0x7F, 0x49, 0x49, 0x49, 0x36, 0x00, 0x00, 0x00]
        font['C'] = [0x3E, 0x41, 0x41, 0x41, 0x22, 0x00, 0x00, 0x00]
        font['D'] = [0x7F, 0x41, 0x41, 0x22, 0x1C, 0x00, 0x00, 0x00]
        font['E'] = [0x7F, 0x49, 0x49, 0x49, 0x41, 0x00, 0x00, 0x00]
        font['F'] = [0x7F, 0x09, 0x09, 0x09, 0x01, 0x00, 0x00, 0x00]
        font['G'] = [0x3E, 0x41, 0x49, 0x49, 0x7A, 0x00, 0x00, 0x00]
        font['H'] = [0x7F, 0x08, 0x08, 0x08, 0x7F, 0x00, 0x00, 0x00]
        font['I'] = [0x00, 0x41, 0x7F, 0x41, 0x00, 0x00, 0x00, 0x00]
        font['J'] = [0x20, 0x40, 0x41, 0x3F, 0x01, 0x00, 0x00, 0x00]
        font['K'] = [0x7F, 0x08, 0x14, 0x22, 0x41, 0x00, 0x00, 0x00]
        font['L'] = [0x7F, 0x40, 0x40, 0x40, 0x40, 0x00, 0x00, 0x00]
        font['M'] = [0x7F, 0x02, 0x0C, 0x02, 0x7F, 0x00, 0x00, 0x00]
        font['N'] = [0x7F, 0x04, 0x08, 0x10, 0x7F, 0x00, 0x00, 0x00]
        font['O'] = [0x3E, 0x41, 0x41, 0x41, 0x3E, 0x00, 0x00, 0x00]
        font['P'] = [0x7F, 0x09, 0x09, 0x09, 0x06, 0x00, 0x00, 0x00]
        font['Q'] = [0x3E, 0x41, 0x51, 0x21, 0x5E, 0x00, 0x00, 0x00]
        font['R'] = [0x7F, 0x09, 0x19, 0x29, 0x46, 0x00, 0x00, 0x00]
        font['S'] = [0x46, 0x49, 0x49, 0x49, 0x31, 0x00, 0x00, 0x00]
        font['T'] = [0x01, 0x01, 0x7F, 0x01, 0x01, 0x00, 0x00, 0x00]
        font['U'] = [0x3F, 0x40, 0x40, 0x40, 0x3F, 0x00, 0x00, 0x00]
        font['V'] = [0x1F, 0x20, 0x40, 0x20, 0x1F, 0x00, 0x00, 0x00]
        font['W'] = [0x3F, 0x40, 0x38, 0x40, 0x3F, 0x00, 0x00, 0x00]
        font['X'] = [0x63, 0x14, 0x08, 0x14, 0x63, 0x00, 0x00, 0x00]
        font['Y'] = [0x07, 0x08, 0x70, 0x08, 0x07, 0x00, 0x00, 0x00]
        font['Z'] = [0x61, 0x51, 0x49, 0x45, 0x43, 0x00, 0x00, 0x00]
        
        # Lowercase letters (simplified)
        font['a'] = [0x20, 0x54, 0x54, 0x54, 0x78, 0x00, 0x00, 0x00]
        font['b'] = [0x7F, 0x48, 0x44, 0x44, 0x38, 0x00, 0x00, 0x00]
        font['c'] = [0x38, 0x44, 0x44, 0x44, 0x20, 0x00, 0x00, 0x00]
        font['d'] = [0x38, 0x44, 0x44, 0x48, 0x7F, 0x00, 0x00, 0x00]
        font['e'] = [0x38, 0x54, 0x54, 0x54, 0x18, 0x00, 0x00, 0x00]
        font['f'] = [0x08, 0x7E, 0x09, 0x01, 0x02, 0x00, 0x00, 0x00]
        font['g'] = [0x0C, 0x52, 0x52, 0x52, 0x3E, 0x00, 0x00, 0x00]
        font['h'] = [0x7F, 0x08, 0x04, 0x04, 0x78, 0x00, 0x00, 0x00]
        font['i'] = [0x00, 0x44, 0x7D, 0x40, 0x00, 0x00, 0x00, 0x00]
        font['j'] = [0x20, 0x40, 0x44, 0x3D, 0x00, 0x00, 0x00, 0x00]
        font['k'] = [0x7F, 0x10, 0x28, 0x44, 0x00, 0x00, 0x00, 0x00]
        font['l'] = [0x00, 0x41, 0x7F, 0x40, 0x00, 0x00, 0x00, 0x00]
        font['m'] = [0x7C, 0x04, 0x18, 0x04, 0x78, 0x00, 0x00, 0x00]
        font['n'] = [0x7C, 0x08, 0x04, 0x04, 0x78, 0x00, 0x00, 0x00]
        font['o'] = [0x38, 0x44, 0x44, 0x44, 0x38, 0x00, 0x00, 0x00]
        font['p'] = [0x7C, 0x14, 0x14, 0x14, 0x08, 0x00, 0x00, 0x00]
        font['q'] = [0x08, 0x14, 0x14, 0x18, 0x7C, 0x00, 0x00, 0x00]
        font['r'] = [0x7C, 0x08, 0x04, 0x04, 0x08, 0x00, 0x00, 0x00]
        font['s'] = [0x48, 0x54, 0x54, 0x54, 0x20, 0x00, 0x00, 0x00]
        font['t'] = [0x04, 0x3F, 0x44, 0x40, 0x20, 0x00, 0x00, 0x00]
        font['u'] = [0x3C, 0x40, 0x40, 0x20, 0x7C, 0x00, 0x00, 0x00]
        font['v'] = [0x1C, 0x20, 0x40, 0x20, 0x1C, 0x00, 0x00, 0x00]
        font['w'] = [0x3C, 0x40, 0x30, 0x40, 0x3C, 0x00, 0x00, 0x00]
        font['x'] = [0x44, 0x28, 0x10, 0x28, 0x44, 0x00, 0x00, 0x00]
        font['y'] = [0x0C, 0x50, 0x50, 0x50, 0x3C, 0x00, 0x00, 0x00]
        font['z'] = [0x44, 0x64, 0x54, 0x4C, 0x44, 0x00, 0x00, 0x00]
        
        # Special characters
        font[' '] = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        font['!'] = [0x00, 0x00, 0x5F, 0x00, 0x00, 0x00, 0x00, 0x00]
        font['?'] = [0x02, 0x01, 0x51, 0x09, 0x06, 0x00, 0x00, 0x00]
        font['.'] = [0x00, 0x60, 0x60, 0x00, 0x00, 0x00, 0x00, 0x00]
        font[','] = [0x00, 0x50, 0x30, 0x00, 0x00, 0x00, 0x00, 0x00]
        font['\''] = [0x00, 0x00, 0x07, 0x00, 0x00, 0x00, 0x00, 0x00]
        font['"'] = [0x00, 0x07, 0x00, 0x07, 0x00, 0x00, 0x00, 0x00]
        font[':'] = [0x00, 0x36, 0x36, 0x00, 0x00, 0x00, 0x00, 0x00]
        font[';'] = [0x00, 0x56, 0x36, 0x00, 0x00, 0x00, 0x00, 0x00]
        font['-'] = [0x08, 0x08, 0x08, 0x08, 0x08, 0x00, 0x00, 0x00]
        font['+'] = [0x08, 0x08, 0x3E, 0x08, 0x08, 0x00, 0x00, 0x00]
        font['='] = [0x14, 0x14, 0x14, 0x14, 0x14, 0x00, 0x00, 0x00]
        font['('] = [0x00, 0x1C, 0x22, 0x41, 0x00, 0x00, 0x00, 0x00]
        font[')'] = [0x00, 0x41, 0x22, 0x1C, 0x00, 0x00, 0x00, 0x00]
        font['['] = [0x00, 0x7F, 0x41, 0x41, 0x00, 0x00, 0x00, 0x00]
        font[']'] = [0x00, 0x41, 0x41, 0x7F, 0x00, 0x00, 0x00, 0x00]
        font['/'] = [0x20, 0x10, 0x08, 0x04, 0x02, 0x00, 0x00, 0x00]
        font['\\'] = [0x02, 0x04, 0x08, 0x10, 0x20, 0x00, 0x00, 0x00]
        font['*'] = [0x14, 0x08, 0x3E, 0x08, 0x14, 0x00, 0x00, 0x00]
        font['#'] = [0x14, 0x7F, 0x14, 0x7F, 0x14, 0x00, 0x00, 0x00]
        font['$'] = [0x24, 0x2A, 0x7F, 0x2A, 0x12, 0x00, 0x00, 0x00]
        font['%'] = [0x23, 0x13, 0x08, 0x64, 0x62, 0x00, 0x00, 0x00]
        font['&'] = [0x36, 0x49, 0x55, 0x22, 0x50, 0x00, 0x00, 0x00]
        font['@'] = [0x32, 0x49, 0x79, 0x41, 0x3E, 0x00, 0x00, 0x00]
        font['^'] = [0x04, 0x02, 0x01, 0x02, 0x04, 0x00, 0x00, 0x00]
        font['_'] = [0x40, 0x40, 0x40, 0x40, 0x40, 0x00, 0x00, 0x00]
        font['<'] = [0x08, 0x14, 0x22, 0x41, 0x00, 0x00, 0x00, 0x00]
        font['>'] = [0x00, 0x41, 0x22, 0x14, 0x08, 0x00, 0x00, 0x00]
        
        # Heart and other symbols
        font['♥'] = [0x0C, 0x1E, 0x3C, 0x78, 0x3C, 0x1E, 0x0C, 0x00]
        font['♦'] = [0x08, 0x1C, 0x3E, 0x7F, 0x3E, 0x1C, 0x08, 0x00]
        font['♣'] = [0x18, 0x18, 0x7E, 0xFF, 0x7E, 0x18, 0x3C, 0x00]
        font['♠'] = [0x08, 0x1C, 0x3E, 0x7F, 0x3E, 0x08, 0x1C, 0x00]
        font['★'] = [0x08, 0x08, 0x3E, 0x1C, 0x1C, 0x3E, 0x08, 0x08]
        font['☺'] = [0x3C, 0x42, 0xA5, 0x81, 0xA5, 0x99, 0x42, 0x3C]
        font['☻'] = [0x3C, 0x7E, 0xDB, 0xFF, 0xDB, 0xE7, 0x7E, 0x3C]
        
        return font
    
    def get_color(self, x: int, mode: str = 'rainbow', base_color: Optional[Tuple[int, int, int]] = None) -> Tuple[int, int, int]:
        """Get color for a pixel based on position and mode"""
        if mode == 'solid' and base_color:
            return base_color
        
        elif mode == 'rainbow':
            # Create rainbow effect across the text
            hue = ((x + self.color_phase) % 100) / 100.0
            r = int(255 * abs(hue * 6 - 3) - 1) if hue < 0.5 else int(255 * (4 - hue * 6))
            g = int(255 * (hue * 6 - 1)) if 0.17 <= hue < 0.5 else int(255 * (3 - abs(hue * 6 - 4)))
            b = int(255 * (hue * 6 - 4)) if hue >= 0.67 else int(255 * (2 - hue * 6)) if hue >= 0.33 else 0
            return (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))
        
        elif mode == 'gradient':
            # Gradient from one color to another
            t = x / self.width
            if base_color:
                # Gradient from base color to white
                r = int(base_color[0] + (255 - base_color[0]) * t)
                g = int(base_color[1] + (255 - base_color[1]) * t)
                b = int(base_color[2] + (255 - base_color[2]) * t)
            else:
                # Blue to red gradient
                r = int(255 * t)
                g = 0
                b = int(255 * (1 - t))
            return (r, g, b)
        
        elif mode == 'fire':
            # Fire effect (red/orange/yellow)
            heat = ((x + self.color_phase) % 50) / 50.0
            if heat < 0.33:
                r = int(heat * 3 * 255)
                g = 0
                b = 0
            elif heat < 0.66:
                r = 255
                g = int((heat - 0.33) * 3 * 255)
                b = 0
            else:
                r = 255
                g = 255
                b = int((heat - 0.66) * 3 * 128)
            return (r, g, b)
        
        elif mode == 'ocean':
            # Ocean effect (blue/cyan/white)
            wave = ((x + self.color_phase) % 60) / 60.0
            r = int(wave * 128)
            g = int(128 + wave * 127)
            b = int(128 + wave * 127)
            return (r, g, b)
        
        elif mode == 'pulse':
            # Pulsing brightness
            pulse = abs(np.sin(self.color_phase * 0.1))
            if base_color:
                r = int(base_color[0] * pulse)
                g = int(base_color[1] * pulse)
                b = int(base_color[2] * pulse)
            else:
                v = int(255 * pulse)
                r = g = b = v
            return (r, g, b)
        
        elif mode == 'sparkle':
            # Random sparkles
            if np.random.random() < 0.1:
                return (255, 255, 255)
            elif base_color:
                return base_color
            else:
                return (100, 100, 255)
        
        else:
            # Default white
            return (255, 255, 255)
    
    def render_text(self, text: str, y_offset: int = 4):
        """Render text to the frame buffer"""
        self.frame_buffer.fill(0)
        
        # Calculate total text width
        text_width = len(text) * self.char_width
        
        # Current x position for rendering (with scroll offset)
        x_pos = int(self.scroll_position)
        
        for char in text:
            if char not in self.font:
                char = '?'  # Unknown character
            
            char_data = self.font[char]
            
            # Render character
            for col in range(5):  # 5 columns per character
                if 0 <= x_pos + col < self.width:
                    # Don't mirror the character, just use normal byte
                    byte = char_data[col] if col < len(char_data) else 0
                    for row in range(8):
                        if byte & (1 << row):
                            # Invert Y axis to fix upside-down text
                            y = self.height - 1 - (y_offset + row)
                            if 0 <= y < self.height:
                                color = self.get_color(x_pos + col, self.color_mode)
                                self.frame_buffer[y, x_pos + col] = color
            
            x_pos += self.char_width
            
            # Stop rendering if we're past the right edge
            if x_pos >= self.width:
                break
        
        return text_width
    
    def update_scroll(self, delta_time: float, text_width: int):
        """Update scroll position"""
        # Scroll from right to left
        self.scroll_position -= self.scroll_speed * delta_time
        
        # Reset when text has scrolled off screen
        if self.scroll_position < -text_width:
            self.scroll_position = self.width
        
        # Update color animation
        self.color_phase += 1
    
    def add_effects(self, effect: str = 'none'):
        """Add special effects to the frame"""
        if effect == 'confetti':
            # Add random colored pixels
            for _ in range(10):
                x = np.random.randint(0, self.width)
                y = np.random.randint(0, self.height)
                color = (
                    np.random.randint(100, 255),
                    np.random.randint(100, 255),
                    np.random.randint(100, 255)
                )
                self.frame_buffer[y, x] = color
        
        elif effect == 'stars':
            # Add twinkling stars
            for _ in range(5):
                x = np.random.randint(0, self.width)
                y = np.random.randint(0, self.height)
                brightness = np.random.randint(150, 255)
                self.frame_buffer[y, x] = [brightness, brightness, brightness]
        
        elif effect == 'border':
            # Add a colored border
            color = self.get_color(int(self.color_phase), 'rainbow')
            # Top and bottom
            self.frame_buffer[0, :] = color
            self.frame_buffer[-1, :] = color
            # Left and right
            self.frame_buffer[:, 0] = color
            self.frame_buffer[:, -1] = color
        
        elif effect == 'fade':
            # Fade edges
            for x in range(10):
                fade = x / 10.0
                self.frame_buffer[:, x] = (self.frame_buffer[:, x] * fade).astype(np.uint8)
                self.frame_buffer[:, -(x+1)] = (self.frame_buffer[:, -(x+1)] * fade).astype(np.uint8)


def find_teensy():
    """Find Teensy serial port - now handled by TeensyConnection"""
    return None  # Auto-detection handled by TeensyConnection


def run_text_scroller(text: str, 
                      duration: Optional[float] = None,
                      speed: float = 30,
                      color_mode: str = 'rainbow',
                      effect: str = 'none',
                      port: Optional[str] = None,
                      test_mode: bool = False):
    """Main function to run the text scroller"""
    
    # Create scroller
    scroller = TextScroller()
    scroller.scroll_speed = speed
    scroller.color_mode = color_mode
    
    # Connect to Teensy if not test mode
    if not test_mode:
        ser = TeensyConnection(port=port)
        if not ser.connect(mode='s'):
            print("Failed to connect to Teensy!")
            return 1
        print(f"Connected to {ser.port}")
    else:
        print("Running in test mode (no hardware)")
        ser = None
    
    print(f"\nScrolling: '{text}'")
    print(f"Color mode: {color_mode}")
    print(f"Speed: {speed} pixels/second")
    print(f"Effect: {effect}")
    print("Press Ctrl+C to stop\n")
    
    # Main loop
    start_time = time.time()
    last_frame_time = start_time
    frame_count = 0
    
    try:
        while True:
            current_time = time.time()
            delta_time = current_time - last_frame_time
            
            # Update scroll position
            text_width = scroller.render_text(text)
            scroller.update_scroll(delta_time, text_width)
            
            # Add effects
            if effect != 'none':
                scroller.add_effects(effect)
            
            # Send to LED matrix
            if not test_mode and ser:
                frame_bytes = b'\xFF\xFE\xFD' + scroller.frame_buffer.flatten().tobytes()
                if not ser.write_frame(frame_bytes):
                    print("Write error, retrying...")
                    continue
            
            frame_count += 1
            last_frame_time = current_time
            
            # Show FPS
            if frame_count % 30 == 0:
                elapsed = current_time - start_time
                fps = frame_count / elapsed if elapsed > 0 else 0
                print(f"FPS: {fps:.1f}", end='\r')
            
            # Check duration
            if duration and (current_time - start_time) >= duration:
                print(f"\nDuration limit reached")
                break
            
            # Frame rate limiting
            time.sleep(1/30)  # 30 FPS target
            
    except KeyboardInterrupt:
        print("\nStopping...")
    
    finally:
        if not test_mode and ser:
            # Clean up connection
            ser.close()
        print("Done")
    
    return 0


def main():
    parser = argparse.ArgumentParser(description='Scrolling text display for LED matrix')
    parser.add_argument('text', nargs='?', default='Happy Birthday!',
                       help='Text to display (default: "Happy Birthday!")')
    parser.add_argument('--speed', type=float, default=30,
                       help='Scroll speed in pixels/second (default: 30)')
    parser.add_argument('--color', choices=['rainbow', 'solid', 'gradient', 'fire', 'ocean', 'pulse', 'sparkle'],
                       default='rainbow', help='Color mode (default: rainbow)')
    parser.add_argument('--effect', choices=['none', 'confetti', 'stars', 'border', 'fade'],
                       default='none', help='Special effect (default: none)')
    parser.add_argument('--duration', type=float,
                       help='Run for specified seconds')
    parser.add_argument('--port', help='Serial port')
    parser.add_argument('--test-mode', action='store_true',
                       help='Run without hardware')
    
    # Preset messages
    parser.add_argument('--preset', choices=['birthday', 'welcome', 'congratulations', 'love', 'party'],
                       help='Use a preset message')
    
    args = parser.parse_args()
    
    # Handle presets
    presets = {
        'birthday': ('🎂 Happy Birthday! 🎉', 'rainbow', 'confetti'),
        'welcome': ('Welcome!', 'gradient', 'stars'),
        'congratulations': ('Congratulations! ⭐', 'fire', 'border'),
        'love': ('I Love You ♥', 'pulse', 'none'),
        'party': ('Party Time! 🎊', 'sparkle', 'confetti')
    }
    
    if args.preset:
        text, color, effect = presets[args.preset]
    else:
        text = args.text
        color = args.color
        effect = args.effect
    
    return run_text_scroller(
        text=text,
        duration=args.duration,
        speed=args.speed,
        color_mode=color,
        effect=effect,
        port=args.port,
        test_mode=args.test_mode
    )


if __name__ == '__main__':
    sys.exit(main())