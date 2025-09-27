# Serial Port Lockup Issues and Solutions

## Problem Analysis

The existing Python scripts lock up the bash shell when run directly because:

### 1. **No Teensy Connected**
- Scripts try to open `/dev/ttyACM0` or similar
- When device doesn't exist, serial.Serial() can hang
- No USB serial devices found (`/dev/ttyACM*`, `/dev/ttyUSB*`)

### 2. **Blocking Operations**
In `stream_to_teensy.py`:
```python
ser = serial.Serial(port, baudrate, timeout=None)  # No timeout!
while True:
    ser.write(data)  # Blocks forever if port not ready
```

### 3. **Infinite Flush Loops**
In `video_streamer.py` and `spectrogram.py`:
```python
self.serial_connection.flush()  # Can block indefinitely
self.serial_connection.reset_output_buffer()  # May hang
```

### 4. **Missing Error Handling**
- No try/except around serial operations
- No timeouts on write operations
- Scripts don't check if port exists before opening

## Why Scripts Lock Up

1. **Opening non-existent ports**: `/dev/ttyACM0` doesn't exist, causing hang
2. **Infinite write loops**: `while True: ser.write()` with no breaks
3. **No write timeouts**: `timeout=None` means wait forever
4. **Buffer operations**: `flush()` waits for all data to transmit

## Current Serial Protocol

From analysis of the code:

### Frame Format
- Start markers: `[0xFF, 0xFE, 0xFD]` (3 bytes)
- Data: 3072 bytes (64x16 pixels × 3 bytes RGB)
- Total frame: 3075 bytes

### Commands
- `'s'`: Enter streaming mode
- `'e'`: Enter effects mode  
- `'t'`: Test mode

### Timing
- Baud rate: 2,000,000 bps
- Frame rate target: 30-60 FPS
- Serial latency: ~1-2ms per frame

## Safe Debugging Approach

Use the new tools created:

```bash
# Test without lockup
./serial_debug.sh test

# Monitor in background (won't freeze terminal)
./serial_debug.sh background
tail -f /tmp/serial_debug_*.log

# Send commands safely
./serial_debug.sh send s
```

## Fix Recommendations

1. **Always use timeouts**:
```python
ser = serial.Serial(port, baudrate, timeout=1, write_timeout=1)
```

2. **Check port exists**:
```python
if not os.path.exists(port):
    print(f"Port {port} not found")
    return
```

3. **Non-blocking writes**:
```python
try:
    ser.write_timeout = 0.1
    ser.write(data)
except serial.SerialTimeoutException:
    pass  # Skip frame
```

4. **Graceful shutdown**:
```python
signal.signal(signal.SIGINT, lambda s,f: ser.close())
```

## Testing Without Teensy

Since no Teensy is currently connected:
1. Scripts default to `/dev/ttyACM0` which doesn't exist
2. This causes immediate hang on `serial.Serial()` call
3. Solution: Check for device first or use virtual serial port for testing