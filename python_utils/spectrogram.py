#!/usr/bin/env python3
"""Robust unified spectrogram visualizer for LED matrix with multiple display modes"""

import sys
import numpy as np
import serial
import serial.tools.list_ports
import time
import argparse
import threading
import queue
import signal
import contextlib
import traceback
from enum import Enum
from typing import Optional, Tuple, List
from datetime import datetime

try:
    import sounddevice as sd
except ImportError:
    print("ERROR: sounddevice not installed. Install with: pip install sounddevice")
    sys.exit(1)

try:
    from scipy import signal as scipy_signal
except ImportError:
    print("ERROR: scipy not installed. Install with: pip install scipy")
    sys.exit(1)


class DisplayMode(Enum):
    """Spectrogram display modes"""
    VERTICAL = "vertical"      # Time flows vertically (bottom=now, top=past)
    HORIZONTAL = "horizontal"   # Time flows horizontally (left=past, right=now)
    REVERSE = "reverse"        # Time flows horizontally (left=now, right=past)


class SafeSpectrogramVisualizer:
    """Thread-safe spectrogram visualizer with robust error handling"""
    
    def __init__(self, device_index: Optional[int] = None, port: Optional[str] = None, brightness: float = 1.0):
        # Display dimensions
        self.width = 64
        self.height = 16
        self.frame_size = self.width * self.height * 3
        self.brightness = max(0.0, min(1.0, brightness))
        
        # Thread safety
        self.lock = threading.RLock()
        self.shutdown_event = threading.Event()
        self.running = False
        
        # Display mode
        self.display_mode = DisplayMode.HORIZONTAL
        
        # Audio settings
        self.sample_rate = 44100
        self.fft_size = 2048
        self.hop_size = 2048
        self.device_index = device_index
        
        # Frequency range
        self.freq_min = 20.0
        self.freq_max = 16000.0
        
        # Initialize buffers
        self._init_buffers()
        
        # Dynamic range and scaling
        self.db_min = -80
        self.db_max = 0
        self.adaptation_rate = 0.05
        self.percentile_low = 10
        self.percentile_high = 90
        
        # Color settings
        self.colormap = 'heat'
        self.fade_exponent = 2.0
        
        # Queue management with bounds
        self.audio_queue = queue.Queue(maxsize=50)
        self.dropped_frames = 0
        
        # Serial port
        self.serial_port = port or self.find_teensy()
        self.serial_connection = None
        self.serial_errors = 0
        self.max_serial_errors = 10
        
        # Audio device validation
        self._validate_audio_device()
        
        # Signal handlers
        self._setup_signal_handlers()
        
        # Calculate frequency mapping
        self._calculate_frequency_bins()
        
        # Statistics
        self.frame_count = 0
        self.start_time = None
        self.last_stats_time = None
        
        # Screenshot capability
        self.screenshot_enabled = False
        self.screenshot_interval = 30  # seconds
        self.last_screenshot_time = None
        self.screenshot_dir = "screenshots"
    
    def _init_buffers(self):
        """Initialize all data buffers"""
        with self.lock:
            # Display buffers
            self.spectrogram_data = np.zeros((self.height, self.width), dtype=np.float32)
            self.display_buffer = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            
            # Raw data for adaptive scaling
            self.raw_spectrogram_data = np.zeros((self.height, self.width), dtype=np.float32)
            self.raw_spectrogram_data.fill(-80)
            
            # Per-frequency scaling parameters
            self.freq_min_values = np.full(self.height, -60.0)
            self.freq_max_values = np.full(self.height, -20.0)
            
            # History for adaptive scaling
            self.freq_history = [[] for _ in range(self.height)]
            self.history_length = 30
    
    def _setup_signal_handlers(self):
        """Setup graceful shutdown handlers"""
        def signal_handler(signum, frame):
            print(f"\nReceived signal {signum}, initiating graceful shutdown...")
            self.shutdown_event.set()
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def _validate_audio_device(self):
        """Validate and setup audio device"""
        try:
            if self.device_index is None:
                self.device_index = sd.default.device[0]
            
            device_info = sd.query_devices(self.device_index, 'input')
            print(f"Audio device: {device_info['name']} (ID: {self.device_index})")
            
            # Validate sample rate
            if device_info['default_samplerate'] != self.sample_rate:
                print(f"Warning: Device default sample rate is {device_info['default_samplerate']}")
                
        except Exception as e:
            print(f"ERROR: Audio device validation failed: {e}")
            print("Use --list-devices to see available devices")
            raise
    
    def find_teensy(self) -> Optional[str]:
        """Find Teensy serial port with error handling"""
        try:
            ports = serial.tools.list_ports.comports()
            for p in ports:
                if any(x in p.description for x in ['Teensy', 'USB Serial', 'ACM']):
                    print(f"Found device on {p.device}: {p.description}")
                    return p.device
            
            # Fallback to first available port
            if ports:
                print(f"No Teensy found, using first available port: {ports[0].device}")
                return ports[0].device
                
        except Exception as e:
            print(f"ERROR: Failed to list serial ports: {e}")
        
        return None
    
    def _calculate_frequency_bins(self):
        """Calculate logarithmic frequency bin mapping with bounds checking"""
        try:
            fft_freqs = np.fft.rfftfreq(self.fft_size, 1/self.sample_rate)
            
            # Logarithmic frequency centers
            self.freq_centers = np.logspace(
                np.log10(self.freq_min),
                np.log10(self.freq_max),
                self.height
            )
            
            # Map to FFT bins
            self.freq_bin_mapping = []
            for i in range(self.height):
                if i == 0:
                    f_low = self.freq_min * 0.9
                else:
                    f_low = np.sqrt(self.freq_centers[i-1] * self.freq_centers[i])
                
                if i == self.height - 1:
                    f_high = self.freq_max * 1.1
                else:
                    f_high = np.sqrt(self.freq_centers[i] * self.freq_centers[i+1])
                
                # Find bins with bounds checking
                bins = np.where((fft_freqs >= f_low) & (fft_freqs < f_high))[0]
                if len(bins) == 0:
                    # Fallback to nearest bin
                    nearest = np.argmin(np.abs(fft_freqs - self.freq_centers[i]))
                    bins = [nearest]
                
                self.freq_bin_mapping.append(bins)
            
            print(f"Frequency mapping: {self.height} bands from {self.freq_min:.0f}Hz to {self.freq_max/1000:.1f}kHz")
            
        except Exception as e:
            print(f"ERROR: Failed to calculate frequency bins: {e}")
            raise
    
    def audio_callback(self, indata, frames, time_info, status):
        """Thread-safe audio callback"""
        try:
            if status:
                print(f"Audio warning: {status}")
            
            if self.running and not self.shutdown_event.is_set():
                # Copy data to avoid reference issues
                audio_data = indata[:, 0].astype(np.float32).copy()
                
                # Try to add to queue, drop if full
                try:
                    self.audio_queue.put_nowait(audio_data)
                except queue.Full:
                    self.dropped_frames += 1
                    if self.dropped_frames % 100 == 0:
                        print(f"\nWarning: Dropped {self.dropped_frames} audio frames")
                        
        except Exception as e:
            print(f"\nERROR in audio callback: {e}")
    
    def connect_serial(self) -> bool:
        """Connect to serial port with retry logic"""
        if not self.serial_port:
            print("No serial port specified")
            return False
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"Connecting to {self.serial_port} (attempt {attempt + 1}/{max_retries})...")
                
                # Close existing connection if any
                if self.serial_connection:
                    try:
                        self.serial_connection.close()
                    except:
                        pass
                
                # Open new connection
                self.serial_connection = serial.Serial(
                    self.serial_port,
                    2000000,
                    timeout=1,
                    write_timeout=1
                )
                
                # Wait for device to be ready
                time.sleep(2)
                
                # Clear buffers
                self.serial_connection.reset_input_buffer()
                self.serial_connection.reset_output_buffer()
                
                # Switch to streaming mode
                self.serial_connection.write(b's')
                self.serial_connection.flush()
                time.sleep(0.5)
                
                print("Serial connection established")
                self.serial_errors = 0
                return True
                
            except serial.SerialException as e:
                print(f"Serial connection failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
            except Exception as e:
                print(f"Unexpected error: {e}")
                break
        
        return False
    
    def send_frame(self, frame_data: np.ndarray) -> bool:
        """Send frame to LED matrix with error handling"""
        if not self.serial_connection:
            return False
        
        try:
            # Apply brightness
            if self.brightness < 0.99:
                frame_data = (frame_data * self.brightness).astype(np.uint8)
            
            frame_bytes = frame_data.flatten().tobytes()
            self.serial_connection.write(b'\xFF\xFE\xFD')  # Frame marker
            self.serial_connection.write(frame_bytes)
            self.serial_connection.flush()
            self.serial_errors = 0
            return True
            
        except serial.SerialTimeoutException:
            self.serial_errors += 1
            print(f"\nSerial timeout (error {self.serial_errors}/{self.max_serial_errors})")
            
        except serial.SerialException as e:
            self.serial_errors += 1
            print(f"\nSerial error: {e} (error {self.serial_errors}/{self.max_serial_errors})")
            
        except Exception as e:
            self.serial_errors += 1
            print(f"\nUnexpected error sending frame: {e}")
        
        # Try to reconnect if too many errors
        if self.serial_errors >= self.max_serial_errors:
            print("Too many serial errors, attempting reconnection...")
            if self.connect_serial():
                self.serial_errors = 0
            else:
                print("Reconnection failed, continuing without display")
                self.serial_connection = None
        
        return False
    
    def get_color(self, value: float) -> Tuple[int, int, int]:
        """Get color for intensity value with bounds checking"""
        value = np.clip(value, 0, 1)
        
        if self.colormap == 'heat':
            # Heat colormap: black -> purple -> red -> orange -> yellow -> white
            if value < 0.1:
                r = g = b = 0
            elif value < 0.25:
                t = (value - 0.1) / 0.15
                r = int(64 * t)
                g = 0
                b = int(32 * t)
            elif value < 0.4:
                t = (value - 0.25) / 0.15
                r = int(64 + 191 * t)
                g = 0
                b = int(32 * (1 - t))
            elif value < 0.6:
                t = (value - 0.4) / 0.2
                r = 255
                g = int(165 * t)
                b = 0
            elif value < 0.8:
                t = (value - 0.6) / 0.2
                r = 255
                g = int(165 + 90 * t)
                b = 0
            else:
                t = (value - 0.8) / 0.2
                r = 255
                g = 255
                b = int(255 * t)
                
        elif self.colormap == 'viridis':
            # Viridis approximation
            r = 68 + value * (59 + value * (111 + value * 17))
            g = 1 + value * (85 + value * (116 + value * 13))
            b = 84 + value * (52 - value * (127 - value * 143))
            
        elif self.colormap == 'plasma':
            # Plasma approximation
            r = 13 + value * (245 + value * (259 - value * 262))
            g = 8 + value * (108 + value * (113 - value * 100))
            b = 135 + value * (158 - value * (325 - value * 332))
            
        else:  # grayscale
            r = g = b = int(value * 255)
        
        # Ensure values are in valid range
        return (
            int(np.clip(r, 0, 255)),
            int(np.clip(g, 0, 255)),
            int(np.clip(b, 0, 255))
        )
    
    def process_audio_chunk(self, audio_data: np.ndarray) -> np.ndarray:
        """Process audio and compute spectrum with error handling"""
        try:
            # Apply window
            window = scipy_signal.windows.hann(len(audio_data))
            windowed = audio_data * window
            
            # Compute FFT
            fft = np.fft.rfft(windowed, n=self.fft_size)
            magnitude = np.abs(fft)
            
            # Convert to dB with numerical stability
            with np.errstate(divide='ignore', invalid='ignore'):
                magnitude_db = 20 * np.log10(magnitude + 1e-10)
                magnitude_db[np.isnan(magnitude_db)] = self.db_min
                magnitude_db[np.isinf(magnitude_db)] = self.db_min
            
            # Map to display frequency bins
            freq_bins = np.zeros(self.height)
            for i, bins in enumerate(self.freq_bin_mapping):
                if len(bins) > 0:
                    # Use median for robustness against outliers
                    freq_bins[i] = np.median(magnitude_db[bins])
            
            return freq_bins
            
        except Exception as e:
            print(f"\nERROR processing audio: {e}")
            return np.full(self.height, self.db_min)
    
    def update_adaptive_scaling(self, spectrum: np.ndarray):
        """Update per-frequency adaptive scaling with bounds checking"""
        try:
            with self.lock:
                for i in range(self.height):
                    # Add to history
                    self.freq_history[i].append(spectrum[i])
                    
                    # Limit history size
                    if len(self.freq_history[i]) > self.history_length:
                        self.freq_history[i].pop(0)
                    
                    # Need minimum samples for statistics
                    if len(self.freq_history[i]) >= 5:
                        history_array = np.array(self.freq_history[i])
                        
                        # Remove outliers
                        valid_values = history_array[history_array > -80]
                        if len(valid_values) > 0:
                            p_low = np.percentile(valid_values, self.percentile_low)
                            p_high = np.percentile(valid_values, self.percentile_high)
                            
                            # Smooth adaptation
                            alpha = self.adaptation_rate
                            self.freq_min_values[i] = (1 - alpha) * self.freq_min_values[i] + alpha * p_low
                            self.freq_max_values[i] = (1 - alpha) * self.freq_max_values[i] + alpha * p_high
                            
                            # Ensure minimum range
                            min_range = 15
                            if self.freq_max_values[i] - self.freq_min_values[i] < min_range:
                                center = (self.freq_max_values[i] + self.freq_min_values[i]) / 2
                                self.freq_min_values[i] = center - min_range / 2
                                self.freq_max_values[i] = center + min_range / 2
                            
                            # Clamp to reasonable bounds
                            self.freq_min_values[i] = np.clip(self.freq_min_values[i], -80, -10)
                            self.freq_max_values[i] = np.clip(self.freq_max_values[i], -60, 0)
                            
        except Exception as e:
            print(f"\nERROR in adaptive scaling: {e}")
    
    def update_spectrogram(self, audio_data: np.ndarray):
        """Update spectrogram display with mode-specific scrolling"""
        try:
            # Process audio
            spectrum = self.process_audio_chunk(audio_data)
            
            # Update adaptive scaling
            self.update_adaptive_scaling(spectrum)
            
            with self.lock:
                if self.display_mode == DisplayMode.VERTICAL:
                    # Vertical mode: shift up, new at bottom
                    self.raw_spectrogram_data[:-1] = self.raw_spectrogram_data[1:]
                    for i in range(self.height):
                        self.raw_spectrogram_data[-1, i] = spectrum[i]
                        
                elif self.display_mode == DisplayMode.HORIZONTAL:
                    # Horizontal mode: shift left, new at right
                    self.raw_spectrogram_data[:, :-1] = self.raw_spectrogram_data[:, 1:]
                    self.raw_spectrogram_data[:, -1] = spectrum
                    
                else:  # REVERSE
                    # Reverse mode: shift right, new at left
                    self.raw_spectrogram_data[:, 1:] = self.raw_spectrogram_data[:, :-1]
                    self.raw_spectrogram_data[:, 0] = spectrum
                
                # Normalize and apply colormap
                self._update_display_buffer()
                
        except Exception as e:
            print(f"\nERROR updating spectrogram: {e}")
            traceback.print_exc()
    
    def _update_display_buffer(self):
        """Update display buffer with normalized and colored data"""
        try:
            # Normalize each frequency band
            for i in range(self.height):
                row_min = self.freq_min_values[i]
                row_max = self.freq_max_values[i]
                row_range = row_max - row_min
                
                if row_range > 1:
                    if self.display_mode == DisplayMode.VERTICAL:
                        # Normalize column for vertical mode
                        normalized = (self.raw_spectrogram_data[:, i] - row_min) / row_range
                    else:
                        # Normalize row for horizontal modes
                        normalized = (self.raw_spectrogram_data[i, :] - row_min) / row_range
                    
                    normalized = np.clip(normalized, 0, 1)
                    
                    # Apply to spectrogram data
                    if self.display_mode == DisplayMode.VERTICAL:
                        self.spectrogram_data[:, i] = normalized
                    else:
                        self.spectrogram_data[i, :] = normalized
                else:
                    # Insufficient range
                    if self.display_mode == DisplayMode.VERTICAL:
                        self.spectrogram_data[:, i] = 0
                    else:
                        self.spectrogram_data[i, :] = 0
            
            # Apply colors with fading
            for y in range(self.height):
                for x in range(self.width):
                    intensity = self.spectrogram_data[y, x]
                    
                    # Apply mode-specific fading
                    if self.display_mode == DisplayMode.VERTICAL:
                        # Fade from bottom (new) to top (old)
                        age_factor = (self.height - 1 - y) / (self.height - 1)
                    elif self.display_mode == DisplayMode.HORIZONTAL:
                        # Fade from right (new) to left (old)
                        age_factor = (self.width - 1 - x) / (self.width - 1)
                    else:  # REVERSE
                        # Fade from left (new) to right (old)
                        age_factor = x / (self.width - 1)
                    
                    # Apply fade
                    fade_factor = np.power(1 - age_factor, self.fade_exponent)
                    faded_intensity = intensity * (0.3 + 0.7 * fade_factor)
                    
                    # Get color
                    r, g, b = self.get_color(faded_intensity)
                    
                    # Store in display buffer (invert y for display)
                    display_y = self.height - 1 - y
                    self.display_buffer[display_y, x] = [r, g, b]
                    
        except Exception as e:
            print(f"\nERROR updating display buffer: {e}")
    
    def save_screenshot(self, prefix="spectrogram"):
        """Save current display buffer as image and ASCII"""
        try:
            # Create screenshots directory if needed
            import os
            os.makedirs(self.screenshot_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Save as numpy array
            np_file = os.path.join(self.screenshot_dir, f"{prefix}_{timestamp}.npy")
            np.save(np_file, self.display_buffer)
            
            # Create ASCII representation
            ascii_file = os.path.join(self.screenshot_dir, f"{prefix}_{timestamp}.txt")
            with open(ascii_file, 'w') as f:
                f.write(f"Spectrogram Screenshot - {timestamp}\n")
                f.write(f"Mode: {self.display_mode.value}\n")
                f.write(f"Colormap: {self.colormap}\n")
                f.write(f"Frequency range: {self.freq_min:.0f}Hz - {self.freq_max:.0f}Hz\n")
                f.write(f"Frame: {self.frame_count}\n")
                f.write("=" * 80 + "\n\n")
                
                # ASCII visualization
                chars = ' .:-=+*#%@'
                for y in range(self.height):
                    row = ""
                    for x in range(self.width):
                        r, g, b = self.display_buffer[y, x]
                        brightness = (r + g + b) / (3 * 255)
                        char_idx = int(brightness * (len(chars) - 1))
                        row += chars[char_idx]
                    f.write(row + "\n")
                
                # Analysis
                f.write("\n" + "=" * 80 + "\n")
                f.write("Analysis:\n")
                
                # Brightness
                brightness = np.mean(self.display_buffer) / 255.0
                f.write(f"  Average brightness: {brightness*100:.1f}%\n")
                
                # Active pixels
                threshold = 20
                active = np.sum(np.any(self.display_buffer > threshold, axis=2))
                total = self.width * self.height
                f.write(f"  Active pixels: {active}/{total} ({active/total*100:.1f}%)\n")
                
                # Frequency activity (rows)
                for i in range(self.height):
                    freq = self.freq_centers[self.height - 1 - i]  # Invert for display
                    activity = np.mean(self.display_buffer[i, :]) / 255.0
                    bar = '█' * int(activity * 20)
                    f.write(f"  {freq:6.0f}Hz: {bar}\n")
            
            # Try to create image if PIL is available
            try:
                from PIL import Image
                img_file = os.path.join(self.screenshot_dir, f"{prefix}_{timestamp}.png")
                
                # Scale up for visibility
                scale = 10
                img_array = np.repeat(np.repeat(self.display_buffer, scale, axis=0), scale, axis=1)
                img = Image.fromarray(img_array, 'RGB')
                img.save(img_file)
                
                print(f"\nScreenshot saved: {img_file}")
            except ImportError:
                print(f"\nScreenshot saved: {ascii_file} (install Pillow for PNG export)")
            
            return ascii_file
            
        except Exception as e:
            print(f"\nError saving screenshot: {e}")
            return None
    
    def print_display_preview(self):
        """Print a live ASCII preview of what's on the display"""
        chars = ' .:-=+*#%@'
        
        # Create border
        print("\n┌" + "─" * self.width + "┐")
        
        for y in range(self.height):
            row = "│"
            for x in range(self.width):
                r, g, b = self.display_buffer[y, x]
                brightness = (r + g + b) / (3 * 255)
                char_idx = int(brightness * (len(chars) - 1))
                row += chars[char_idx]
            row += "│"
            print(row)
        
        print("└" + "─" * self.width + "┘")
    
    def cleanup(self):
        """Cleanup resources safely"""
        print("\nCleaning up resources...")
        
        self.running = False
        self.shutdown_event.set()
        
        # Close serial connection
        if self.serial_connection:
            try:
                self.serial_connection.write(b'e')  # Switch to effects mode
                time.sleep(0.1)
                self.serial_connection.close()
                print("Serial connection closed")
            except:
                pass
        
        # Clear queue
        try:
            while not self.audio_queue.empty():
                self.audio_queue.get_nowait()
        except:
            pass
        
        print("Cleanup complete")
    
    def run(self, duration: Optional[float] = None, test_mode: bool = False):
        """Main visualization loop with comprehensive error handling"""
        self.test_mode = test_mode
        
        # Setup serial connection
        if not test_mode:
            if not self.serial_port:
                print("ERROR: No serial port available")
                return
            
            if not self.connect_serial():
                print("ERROR: Failed to establish serial connection")
                if not input("Continue in test mode? (y/n): ").lower().startswith('y'):
                    return
                self.test_mode = True
        
        # Initialize statistics
        self.frame_count = 0
        self.start_time = time.time()
        self.last_stats_time = self.start_time
        
        # Audio stream context manager
        stream = None
        
        try:
            # Start audio stream
            print("Starting audio stream...")
            self.running = True
            
            stream = sd.InputStream(
                callback=self.audio_callback,
                device=self.device_index,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=512,
                latency='low'
            )
            stream.start()
            print("Audio stream started successfully")
            
            # Display mode info
            mode_info = {
                DisplayMode.VERTICAL: "Vertical (bottom=now, top=past)",
                DisplayMode.HORIZONTAL: "Horizontal (left=past, right=now)",
                DisplayMode.REVERSE: "Reverse (left=now, right=past)"
            }
            
            print(f"\nVisualization mode: {mode_info[self.display_mode]}")
            print(f"Frequency range: {self.freq_min:.0f}Hz - {self.freq_max/1000:.1f}kHz")
            print(f"Color scheme: {self.colormap}")
            print("Press Ctrl+C to stop\n")
            
            # Audio accumulator
            accumulated_samples = []
            
            # Main loop
            while self.running and not self.shutdown_event.is_set():
                try:
                    # Get audio data with timeout
                    audio_chunk = self.audio_queue.get(timeout=0.1)
                    accumulated_samples.append(audio_chunk)
                    
                    # Process when we have enough samples
                    total_samples = sum(len(chunk) for chunk in accumulated_samples)
                    
                    if total_samples >= self.hop_size:
                        # Combine chunks
                        combined = np.concatenate(accumulated_samples)
                        
                        # Extract window for FFT
                        if len(combined) >= self.fft_size:
                            audio_window = combined[-self.fft_size:]
                        else:
                            # Pad if needed
                            audio_window = np.pad(combined, (self.fft_size - len(combined), 0))
                        
                        # Update spectrogram
                        self.update_spectrogram(audio_window)
                        
                        # Keep overlap samples
                        if len(combined) > self.hop_size:
                            accumulated_samples = [combined[self.hop_size:]]
                        else:
                            accumulated_samples = []
                        
                        # Send to display
                        if not self.test_mode:
                            with self.lock:
                                self.send_frame(self.display_buffer)
                        
                        self.frame_count += 1
                        
                        # Update statistics
                        current_time = time.time()
                        if current_time - self.last_stats_time >= 1.0:
                            elapsed = current_time - self.start_time
                            fps = self.frame_count / elapsed if elapsed > 0 else 0
                            
                            status = f"FPS: {fps:.1f} | Frames: {self.frame_count}"
                            if self.dropped_frames > 0:
                                status += f" | Dropped: {self.dropped_frames}"
                            if self.serial_errors > 0:
                                status += f" | Serial errors: {self.serial_errors}"
                            
                            print(f"\r{status}", end='', flush=True)
                            self.last_stats_time = current_time
                        
                        # Auto-screenshot if enabled
                        if self.screenshot_enabled:
                            if self.last_screenshot_time is None or \
                               (current_time - self.last_screenshot_time) >= self.screenshot_interval:
                                self.save_screenshot()
                                self.last_screenshot_time = current_time
                    
                    # Check duration limit
                    if duration and (time.time() - self.start_time) >= duration:
                        print(f"\n\nDuration limit of {duration}s reached")
                        break
                        
                except queue.Empty:
                    # No audio data available
                    continue
                    
                except KeyboardInterrupt:
                    print("\n\nKeyboard interrupt received")
                    break
                    
                except Exception as e:
                    print(f"\nERROR in main loop: {e}")
                    if input("Continue? (y/n): ").lower().startswith('n'):
                        break
                        
        except Exception as e:
            print(f"\nFATAL ERROR: {e}")
            traceback.print_exc()
            
        finally:
            # Stop audio stream
            if stream:
                try:
                    stream.stop()
                    stream.close()
                    print("\nAudio stream stopped")
                except:
                    pass
            
            # Final statistics
            if self.frame_count > 0:
                total_time = time.time() - self.start_time
                avg_fps = self.frame_count / total_time
                print(f"\nSession statistics:")
                print(f"  Total frames: {self.frame_count}")
                print(f"  Duration: {total_time:.1f}s")
                print(f"  Average FPS: {avg_fps:.1f}")
                if self.dropped_frames > 0:
                    print(f"  Dropped frames: {self.dropped_frames}")
            
            # Cleanup
            self.cleanup()


def list_audio_devices():
    """List available audio input devices"""
    print("\nAvailable audio input devices:")
    print("-" * 60)
    
    try:
        devices = sd.query_devices()
        input_devices = []
        
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append(i)
                marker = " [DEFAULT]" if i == sd.default.device[0] else ""
                print(f"  [{i:2d}] {device['name']}{marker}")
                print(f"       Channels: {device['max_input_channels']}")
                print(f"       Sample Rate: {device['default_samplerate']:.0f} Hz")
        
        if not input_devices:
            print("  No input devices found!")
            
    except Exception as e:
        print(f"ERROR listing devices: {e}")
    
    print("-" * 60)


def list_serial_ports():
    """List available serial ports"""
    print("\nAvailable serial ports:")
    print("-" * 60)
    
    try:
        ports = serial.tools.list_ports.comports()
        if ports:
            for p in ports:
                print(f"  {p.device}")
                print(f"    Description: {p.description}")
                if p.manufacturer:
                    print(f"    Manufacturer: {p.manufacturer}")
        else:
            print("  No serial ports found!")
            
    except Exception as e:
        print(f"ERROR listing ports: {e}")
    
    print("-" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Robust unified spectrogram visualizer for LED matrix',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Display modes:
  vertical    Time flows vertically (bottom=now, top=past)
  horizontal  Time flows horizontally (left=past, right=now)  
  reverse     Time flows horizontally (left=now, right=past)

Color schemes:
  heat        Black -> Purple -> Red -> Orange -> Yellow -> White
  viridis     Purple -> Blue -> Green -> Yellow
  plasma      Purple -> Pink -> Orange -> Yellow
  gray        Grayscale

Examples:
  %(prog)s                        # Use defaults
  %(prog)s --mode vertical        # Vertical scrolling
  %(prog)s --color plasma         # Plasma colors
  %(prog)s --device 2             # Use specific audio device
  %(prog)s --test-mode            # Run without hardware
  %(prog)s --list-devices         # Show available devices
        """
    )
    
    # Display options
    parser.add_argument('--mode', 
                       choices=['vertical', 'horizontal', 'reverse'],
                       default='horizontal',
                       help='Display mode (default: horizontal)')
    
    parser.add_argument('--color',
                       choices=['heat', 'viridis', 'plasma', 'gray'],
                       default='heat',
                       help='Color scheme (default: heat)')
    
    parser.add_argument('--fade',
                       type=float,
                       default=2.0,
                       help='Fade exponent for time decay (default: 2.0)')
    
    # Audio options
    parser.add_argument('--device',
                       type=int,
                       help='Audio input device index')
    
    parser.add_argument('--freq-min',
                       type=float,
                       default=20,
                       help='Minimum frequency in Hz (default: 20)')
    
    parser.add_argument('--freq-max',
                       type=float,
                       default=16000,
                       help='Maximum frequency in Hz (default: 16000)')
    
    # Serial options
    parser.add_argument('--port',
                       help='Serial port (e.g., /dev/ttyACM0, COM3)')
    
    # Runtime options
    parser.add_argument('--duration',
                       type=float,
                       help='Run for specified seconds')
    
    parser.add_argument('--test-mode',
                       action='store_true',
                       help='Run without hardware')
    
    # Screenshot options
    parser.add_argument('--screenshot',
                       action='store_true',
                       help='Enable periodic screenshots')
    
    parser.add_argument('--screenshot-interval',
                       type=float,
                       default=30,
                       help='Screenshot interval in seconds (default: 30)')
    
    parser.add_argument('--preview',
                       action='store_true',
                       help='Show ASCII preview of display')
    
    # Information options
    parser.add_argument('--list-devices',
                       action='store_true',
                       help='List audio devices and exit')
    
    parser.add_argument('--list-ports',
                       action='store_true',
                       help='List serial ports and exit')
    parser.add_argument('--brightness', type=float, default=1.0,
                       help='Brightness level (0.0-1.0, default: 1.0). Use 0.3 for nighttime')
    
    args = parser.parse_args()
    
    # Handle information requests
    if args.list_devices:
        list_audio_devices()
        return 0
    
    if args.list_ports:
        list_serial_ports()
        return 0
    
    # Create and configure visualizer
    try:
        visualizer = SafeSpectrogramVisualizer(
            device_index=args.device,
            port=args.port,
            brightness=args.brightness
        )
        
        # Set display mode
        visualizer.display_mode = DisplayMode(args.mode)
        
        # Set visualization parameters
        visualizer.colormap = args.color
        visualizer.fade_exponent = args.fade
        visualizer.freq_min = args.freq_min
        visualizer.freq_max = args.freq_max
        
        # Recalculate frequency bins if range changed
        if args.freq_min != 20 or args.freq_max != 16000:
            visualizer._calculate_frequency_bins()
        
        # Configure screenshot options
        visualizer.screenshot_enabled = args.screenshot
        visualizer.screenshot_interval = args.screenshot_interval
        
        # Run visualizer
        visualizer.run(
            duration=args.duration,
            test_mode=args.test_mode
        )
        
        # Show preview at end if requested
        if args.preview:
            print("\nFinal display state:")
            visualizer.print_display_preview()
        
        return 0
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        return 1
        
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())