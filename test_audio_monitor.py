#!/usr/bin/env python3
"""Test audio monitoring to debug VU meter issues"""

import sounddevice as sd
import numpy as np
import time

def test_device(device_id, duration=3):
    """Test a specific audio device"""
    try:
        device_info = sd.query_devices(device_id)
        print(f"\nTesting device {device_id}: {device_info['name']}")
        print(f"  Channels: in={device_info['max_input_channels']}, out={device_info['max_output_channels']}")
        
        if device_info['max_input_channels'] == 0:
            print("  No input channels - skipping")
            return
        
        channels = min(2, device_info['max_input_channels'])
        levels = []
        
        def callback(indata, frames, time_info, status):
            if status:
                print(f"  Status: {status}")
            # Calculate RMS level
            rms = np.sqrt(np.mean(indata**2))
            levels.append(rms)
        
        with sd.InputStream(device=device_id, channels=channels, 
                          callback=callback, samplerate=44100):
            print(f"  Recording for {duration} seconds...")
            time.sleep(duration)
        
        if levels:
            avg_level = np.mean(levels)
            max_level = np.max(levels)
            print(f"  Average level: {avg_level:.6f}")
            print(f"  Max level: {max_level:.6f}")
            print(f"  Estimated dB: {20*np.log10(max_level+1e-10):.1f} dB")
            
            if avg_level < 0.0001:
                print("  ⚠️  Very low/no signal detected")
            elif avg_level > 0.01:
                print("  ✓ Good signal detected!")
            else:
                print("  ⚠️  Weak signal")
                
    except Exception as e:
        print(f"  Error: {e}")

# Test various devices
print("Testing audio devices for signal...")
print("Play some audio during this test!\n")

# Test PulseAudio
test_device(24, 2)  # pulse

# Test Xonar devices
test_device(6, 2)   # Xonar USB Audio
test_device(7, 2)   # Xonar USB Audio #1

# Test default
test_device(29, 2)  # default

print("\n✓ Test complete!")
print("\nUse the device with 'Good signal detected' for the VU meter.")