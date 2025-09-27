#!/usr/bin/env python3
"""
Direct YouTube to LED Matrix Streamer
Streams YouTube videos directly to LED matrix without downloading
"""

import sys
import subprocess
import argparse
import serial
import serial.tools.list_ports
import time
import numpy as np

class YouTubeStreamer:
    def __init__(self, port=None, baudrate=2000000):
        """Initialize streamer with serial connection"""
        self.width = 64
        self.height = 16
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
    
    def send_frame(self, frame_data):
        """Send a frame to the Teensy"""
        # Send start marker
        self.serial_port.write(b'\xFF\xFE\xFD')
        
        # Send frame data in chunks
        chunk_size = 128
        for i in range(0, len(frame_data), chunk_size):
            chunk = frame_data[i:i+chunk_size]
            self.serial_port.write(chunk)
            # Extra delay for first panel (bottom-left)
            if i < 768:
                time.sleep(0.002)
            elif i % 512 == 0:
                time.sleep(0.001)
        
        self.serial_port.flush()
    
    def stream_youtube(self, url, quality='360p', gamma=1.4, contrast=1.3, brightness=0):
        """Stream YouTube video directly to LED matrix"""
        
        # Quality settings for faster streaming
        quality_formats = {
            '144p': 'worst[height<=144]',
            '240p': 'worst[height<=240]',
            '360p': 'best[height<=360]',
            '480p': 'best[height<=480]',
            '720p': 'best[height<=720]'
        }
        
        format_spec = quality_formats.get(quality, quality_formats['360p'])
        
        print(f"Streaming: {url}")
        print(f"Quality: {quality}, Gamma: {gamma}, Contrast: {contrast}")
        
        # Build yt-dlp command to output to stdout
        yt_dlp_cmd = [
            'yt-dlp',
            '--cookies-from-browser', 'chrome',
            '-f', format_spec,
            '-o', '-',  # Output to stdout
            '--no-playlist',  # Don't download playlists
            url
        ]
        
        # Build ffmpeg command to process video
        # Apply gamma and contrast corrections
        filter_complex = (
            f'scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,'
            f'pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2,'
            f'eq=contrast={contrast}:gamma={gamma}'
        )
        
        if brightness != 0:
            filter_complex += f':brightness={brightness/100.0}'
        
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', 'pipe:0',  # Input from stdin
            '-vf', filter_complex,
            '-r', '30',  # 30 fps output
            '-f', 'rawvideo',
            '-pix_fmt', 'rgb24',
            '-'  # Output to stdout
        ]
        
        # Start the pipeline
        print("Starting stream... (Press Ctrl+C to stop)")
        
        try:
            # Start yt-dlp process
            print("Fetching video stream...")
            yt_dlp_proc = subprocess.Popen(yt_dlp_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # Start ffmpeg process
            print("Processing video...")
            ffmpeg_proc = subprocess.Popen(
                ffmpeg_cmd, 
                stdin=yt_dlp_proc.stdout,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Close yt-dlp stdout in parent (important for proper piping)
            yt_dlp_proc.stdout.close()
            
            frame_size = self.width * self.height * 3
            frame_count = 0
            start_time = time.time()
            
            while True:
                # Read frame from ffmpeg
                frame_data = ffmpeg_proc.stdout.read(frame_size)
                if len(frame_data) != frame_size:
                    print("\nStream ended or interrupted")
                    break
                
                # Send to LED matrix
                self.send_frame(frame_data)
                
                frame_count += 1
                
                # Show progress
                if frame_count % 30 == 0:
                    elapsed = time.time() - start_time
                    fps = frame_count / elapsed if elapsed > 0 else 0
                    print(f"Streaming: {frame_count} frames, {fps:.1f} FPS", end='\r')
                
                # Maintain frame rate
                target_time = frame_count / 30.0
                actual_time = time.time() - start_time
                if target_time > actual_time:
                    time.sleep(target_time - actual_time)
        
        except KeyboardInterrupt:
            print("\nStopping stream...")
        finally:
            # Clean up processes
            if 'ffmpeg_proc' in locals():
                ffmpeg_proc.terminate()
            if 'yt_dlp_proc' in locals():
                yt_dlp_proc.terminate()
            print(f"\nStreamed {frame_count} frames")

def main():
    parser = argparse.ArgumentParser(description='Stream YouTube directly to LED matrix')
    parser.add_argument('url', help='YouTube URL')
    parser.add_argument('--port', help='Serial port (auto-detect if not specified)')
    parser.add_argument('--quality', default='360p', choices=['144p', '240p', '360p', '480p', '720p'],
                        help='Video quality (default: 360p)')
    parser.add_argument('--gamma', type=float, default=1.4,
                        help='Gamma correction (default: 1.4)')
    parser.add_argument('--contrast', type=float, default=1.3,
                        help='Contrast adjustment (default: 1.3)')
    parser.add_argument('--brightness', type=int, default=0,
                        help='Brightness adjustment -100 to 100 (default: 0)')
    
    args = parser.parse_args()
    
    streamer = YouTubeStreamer(args.port)
    streamer.stream_youtube(args.url, args.quality, args.gamma, args.contrast, args.brightness)

if __name__ == '__main__':
    main()