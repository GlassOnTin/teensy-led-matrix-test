#!/usr/bin/env python3
"""
Video to LED Matrix Streamer
Processes video files and streams them to Teensy-controlled LED matrix
"""

import sys
import time
import serial
import serial.tools.list_ports
import numpy as np
import subprocess
import argparse
from pathlib import Path
import cv2

class VideoStreamer:
    def __init__(self, port=None, baudrate=2000000):
        """Initialize video streamer with serial connection"""
        self.width = 64
        self.height = 16
        self.fps = 30
        self.serial_port = None
        
        if port is None:
            # Auto-detect Teensy
            ports = serial.tools.list_ports.comports()
            for p in ports:
                if 'Teensy' in p.description or 'USB Serial' in p.description:
                    port = p.device
                    print(f"Found Teensy on {port}")
                    break
            
            if port is None:
                print("No Teensy found. Available ports:")
                for p in ports:
                    print(f"  {p.device}: {p.description}")
                sys.exit(1)
        
        try:
            self.serial_port = serial.Serial(port, baudrate, timeout=1)
            time.sleep(2)  # Wait for Teensy to reset
            print(f"Connected to {port} at {baudrate} baud")
        except Exception as e:
            print(f"Failed to open serial port: {e}")
            sys.exit(1)
    
    def process_video_ffmpeg(self, video_path, start_time=0, duration=None):
        """Use ffmpeg to extract and resize frames"""
        video_path = Path(video_path)
        if not video_path.exists():
            print(f"Video file not found: {video_path}")
            return
        
        # Build ffmpeg command
        cmd = [
            'ffmpeg',
            '-i', str(video_path),
            '-ss', str(start_time),  # Start time
        ]
        
        if duration:
            cmd.extend(['-t', str(duration)])  # Duration
        
        cmd.extend([
            '-vf', f'scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2',
            '-r', str(self.fps),  # Output framerate
            '-f', 'rawvideo',
            '-pix_fmt', 'rgb24',
            '-'  # Output to stdout
        ])
        
        print(f"Processing video: {video_path.name}")
        print(f"Resolution: {self.width}x{self.height} @ {self.fps}fps")
        
        # Start ffmpeg process
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        
        frame_size = self.width * self.height * 3  # RGB24
        frame_count = 0
        start = time.time()
        
        try:
            while True:
                # Read frame from ffmpeg
                raw_frame = process.stdout.read(frame_size)
                if len(raw_frame) != frame_size:
                    break
                
                # Convert to numpy array
                frame = np.frombuffer(raw_frame, dtype=np.uint8)
                frame = frame.reshape((self.height, self.width, 3))
                
                # Send frame to Teensy
                self.send_frame(frame)
                
                frame_count += 1
                
                # Print progress
                if frame_count % 30 == 0:
                    elapsed = time.time() - start
                    actual_fps = frame_count / elapsed if elapsed > 0 else 0
                    print(f"Frame {frame_count}, FPS: {actual_fps:.1f}", end='\r')
                
                # Maintain target framerate
                target_time = frame_count / self.fps
                actual_time = time.time() - start
                if target_time > actual_time:
                    time.sleep(target_time - actual_time)
        
        except KeyboardInterrupt:
            print("\nStopped by user")
        finally:
            process.terminate()
            print(f"\nStreamed {frame_count} frames")
    
    def process_video_opencv(self, video_path, start_time=0, duration=None, gamma=1.4, crop_mode='center', brightness=0, contrast=1.3, loop=False, flip=False, blackout=0):
        """Use OpenCV to process video with effects"""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"Failed to open video: {video_path}")
            return
        
        # Get video properties
        video_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        # Set start position
        if start_time > 0:
            start_frame = int(start_time * video_fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        
        print(f"Processing video: {video_path}")
        print(f"Original: {int(cap.get(3))}x{int(cap.get(4))} @ {video_fps:.1f}fps")
        print(f"Output: {self.width}x{self.height} @ {self.fps}fps")
        print(f"Gamma: {gamma}, Brightness: +{brightness}, Contrast: {contrast}x, Crop mode: {crop_mode}")
        
        # Build gamma lookup table
        # For LED displays: gamma > 1 darkens mid-tones, gamma < 1 brightens
        gamma_table = np.array([((i / 255.0) ** gamma) * 255 
                               for i in np.arange(0, 256)]).astype("uint8")
        
        frame_count = 0
        start = time.time()
        end_time = start + duration if duration else float('inf')
        
        try:
            while time.time() < end_time:
                ret, frame = cap.read()
                if not ret:
                    if loop:
                        # Loop video
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        continue
                    else:
                        break
                
                # Crop or letterbox based on mode
                h, w = frame.shape[:2]
                aspect = w / h
                target_aspect = self.width / self.height
                
                if crop_mode == 'center':
                    # Center crop - fill the display
                    if aspect > target_aspect:
                        # Video is wider - crop width
                        new_height = h
                        new_width = int(h * target_aspect)
                        x_start = (w - new_width) // 2
                        frame = frame[:, x_start:x_start+new_width]
                    else:
                        # Video is taller - crop height
                        new_width = w
                        new_height = int(w / target_aspect)
                        y_start = (h - new_height) // 2
                        frame = frame[y_start:y_start+new_height, :]
                    
                    # Resize to exact display size
                    canvas = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)
                else:
                    # Letterbox mode (original behavior)
                    if aspect > target_aspect:
                        # Video is wider - fit to width
                        new_width = self.width
                        new_height = int(self.width / aspect)
                    else:
                        # Video is taller - fit to height
                        new_height = self.height
                        new_width = int(self.height * aspect)
                    
                    # Resize
                    frame = cv2.resize(frame, (new_width, new_height), interpolation=cv2.INTER_AREA)
                    
                    # Create canvas and center the frame
                    canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)
                    y_offset = (self.height - new_height) // 2
                    x_offset = (self.width - new_width) // 2
                    canvas[y_offset:y_offset+new_height, x_offset:x_offset+new_width] = frame
                
                # Convert BGR to RGB
                canvas = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
                
                # Flip if requested (for ceiling mount)
                if flip:
                    canvas = cv2.flip(canvas, 0)  # Vertical flip
                
                # Apply contrast adjustment first (no brightness offset to preserve blacks)
                canvas = cv2.convertScaleAbs(canvas, alpha=contrast, beta=0)
                
                # Apply gamma correction to lift mid-tones without affecting blacks
                canvas = cv2.LUT(canvas, gamma_table)
                
                # Optional: Apply a black level threshold to ensure true blacks
                if brightness > 0:
                    # Only brighten pixels above a threshold to preserve blacks
                    mask = cv2.cvtColor(canvas, cv2.COLOR_RGB2GRAY) > 10
                    canvas[mask] = cv2.add(canvas[mask], brightness)
                
                # Blackout leftmost columns if requested
                if blackout > 0:
                    canvas[:, :blackout] = 0
                
                # Apply effects (optional)
                # canvas = self.apply_effects(canvas, frame_count)
                
                # Send frame
                self.send_frame(canvas)
                
                frame_count += 1
                
                # Print progress
                if frame_count % 30 == 0:
                    elapsed = time.time() - start
                    actual_fps = frame_count / elapsed if elapsed > 0 else 0
                    print(f"Frame {frame_count}/{total_frames}, FPS: {actual_fps:.1f}", end='\r')
                
                # Maintain framerate
                target_time = frame_count / self.fps
                actual_time = time.time() - start
                if target_time > actual_time:
                    time.sleep(target_time - actual_time)
        
        except KeyboardInterrupt:
            print("\nStopped by user")
        finally:
            cap.release()
            print(f"\nStreamed {frame_count} frames")
    
    def apply_effects(self, frame, frame_num):
        """Apply visual effects to frame"""
        # Example: Add some color cycling
        hue_shift = (frame_num * 2) % 180
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
        hsv[:, :, 0] = (hsv[:, :, 0] + hue_shift) % 180
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
    
    def send_frame(self, frame, blackout_columns=1):
        """Send a frame to the Teensy"""
        # Black out first N columns of both left panels to reduce flicker
        if blackout_columns > 0:
            # Top-left panel (Panel 1): rows 0-7, columns 0-31
            frame[0:8, 0:blackout_columns] = 0  # Set to black
            # Bottom-left panel (Panel 3): rows 8-15, columns 0-31
            frame[8:16, 0:blackout_columns] = 0  # Set to black
        
        # Protocol: Start byte + frame data
        # Flatten frame data and ensure it's in RGB order
        data = frame.flatten()
        
        # Send start marker
        self.serial_port.write(b'\xFF\xFE\xFD')  # Start marker
        
        # Send frame data in smaller chunks with better flow control
        chunk_size = 128  # Smaller chunks
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i+chunk_size]
            self.serial_port.write(bytes(chunk))
            # More frequent delays for panel 1 (bottom-left) data
            # Panel 1 starts at pixel 0 and has issues with long wire
            if i < 768:  # First panel data (256 pixels * 3 bytes)
                time.sleep(0.002)  # Extra delay for panel 1
            elif i % 512 == 0:
                time.sleep(0.001)  # Regular delay for other panels
        
        # Wait for data to be transmitted
        self.serial_port.flush()
    
    def send_test_pattern(self):
        """Send a test pattern to verify communication"""
        print("Sending test pattern for 10 seconds...")
        print(f"Connected to port: {self.serial_port.name}")
        start_time = time.time()
        frames_sent = 0
        
        while time.time() - start_time < 10:  # Run for 10 seconds
            i = frames_sent
            frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            
            # Create moving rainbow
            for x in range(self.width):
                hue = (x + i * 5) % 256
                for y in range(self.height):
                    # Simple HSV to RGB (approximate)
                    frame[y, x] = [hue, 255 - hue, (hue + 128) % 256]
            
            self.send_frame(frame)
            frames_sent += 1
            
            if frames_sent % 30 == 0:
                print(f"Sent {frames_sent} frames...")
            
            time.sleep(1/30)  # 30 FPS
        
        print(f"Test pattern complete - sent {frames_sent} frames")
    
    def stream_webcam(self, duration=None):
        """Stream from webcam"""
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Failed to open webcam")
            return
        
        print("Streaming from webcam (press Ctrl+C to stop)")
        frame_count = 0
        start = time.time()
        end_time = start + duration if duration else float('inf')
        
        try:
            while time.time() < end_time:
                ret, frame = cap.read()
                if not ret:
                    continue
                
                # Resize and convert
                frame = cv2.resize(frame, (self.width, self.height), interpolation=cv2.INTER_AREA)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                self.send_frame(frame)
                frame_count += 1
                
                if frame_count % 30 == 0:
                    elapsed = time.time() - start
                    actual_fps = frame_count / elapsed if elapsed > 0 else 0
                    print(f"FPS: {actual_fps:.1f}", end='\r')
                
                # Maintain 30 FPS
                target_time = frame_count / 30
                actual_time = time.time() - start
                if target_time > actual_time:
                    time.sleep(target_time - actual_time)
        
        except KeyboardInterrupt:
            print("\nStopped")
        finally:
            cap.release()

def main():
    parser = argparse.ArgumentParser(description='Stream video to LED matrix')
    parser.add_argument('input', nargs='?', help='Video file path or "webcam" or "test"')
    parser.add_argument('--port', help='Serial port (auto-detect if not specified)')
    parser.add_argument('--baud', type=int, default=2000000, help='Baud rate (default: 2000000)')
    parser.add_argument('--fps', type=int, default=30, help='Target FPS (default: 30)')
    parser.add_argument('--start', type=float, default=0, help='Start time in seconds')
    parser.add_argument('--duration', type=float, help='Duration in seconds')
    parser.add_argument('--opencv', action='store_true', help='Use OpenCV instead of ffmpeg')
    parser.add_argument('--gamma', type=float, default=1.4, help='Gamma correction (default: 1.4, lower=brighter, try 1.0-2.2)')
    parser.add_argument('--brightness', type=int, default=0, help='Brightness adjustment (-100 to 100, default: 0, preserves blacks)')
    parser.add_argument('--contrast', type=float, default=1.3, help='Contrast multiplier (0.1 to 3.0, default: 1.3)')
    parser.add_argument('--crop', action='store_true', help='Center crop to fill display (default)')
    parser.add_argument('--letterbox', action='store_true', help='Letterbox to preserve aspect ratio')
    parser.add_argument('--loop', action='store_true', help='Loop video continuously')
    parser.add_argument('--flip', action='store_true', help='Flip video vertically (for ceiling mount)')
    parser.add_argument('--blackout', type=int, default=0, help='Blackout N leftmost columns (default: 0)')
    
    args = parser.parse_args()
    
    # Determine crop mode
    crop_mode = 'letterbox' if args.letterbox else 'center'
    
    # Create streamer
    streamer = VideoStreamer(args.port, args.baud)
    streamer.fps = args.fps
    
    if not args.input or args.input == 'test':
        # Test pattern
        streamer.send_test_pattern()
    elif args.input == 'webcam':
        # Webcam stream
        streamer.stream_webcam(args.duration)
    else:
        # Video file - always use OpenCV now for gamma and crop support
        streamer.process_video_opencv(args.input, args.start, args.duration, args.gamma, crop_mode, 
                                     args.brightness, args.contrast, args.loop, args.flip, args.blackout)

if __name__ == '__main__':
    main()