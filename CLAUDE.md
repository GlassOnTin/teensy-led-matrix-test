# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Teensy 4.0 LED matrix control system for driving a 64x16 display composed of 4 SK6812 LED panels (8x32 each). The system supports real-time video streaming, built-in animation effects, web-based casting, and interactive visualizations.

## Quick Setup

```bash
# One-time setup (installs everything)
./setup.sh

# Upload firmware to Teensy (press button when prompted)
platformio run --target upload
```


## Main Command Interface

The `led-matrix` script is the primary interface - a unified command wrapper that handles all functionality:

```bash
# Test connection
./led-matrix test --pattern

# Play video
./led-matrix video movie.mp4 --loop --flip

# Audio visualizations
./led-matrix audio              # Spectrogram
./led-matrix vu                 # VU meter
./led-matrix phase              # Phase/oscilloscope

# Web interface (family-friendly)
./led-matrix web                # Text display web interface
./led-matrix api                # Start REST API server

# Built-in animations
./led-matrix fireworks
./led-matrix effects            # Auto-cycling effects
./led-matrix cycle              # Configurable auto-cycle

# Text and media
./led-matrix text "Hello World"
./led-matrix youtube "URL"
./led-matrix webcam

# Aircraft tracking (ADSB)
./led-matrix aircraft           # Stream aircraft ticker from tar1090
./led-matrix aircraft-web       # Web preview interface on port 5555
```

## Development Commands

### Firmware Development
```bash
platformio run                  # Compile
platformio run --target upload  # Upload (press button when prompted)
platformio device monitor       # Serial monitor (115200 baud)
platformio run --target clean   # Clean build
```

### Testing and Debugging
```bash
# Connection testing
./led-matrix test               # Basic connection
./led-matrix test --pattern     # Visual test patterns

# Serial debugging
./serial_debug.sh               # Debug serial communication
python3 python_utils/test_serial.py --list-ports  # List available ports
```

### Service Installation
```bash
# Install web cast server as systemd service
./install_cast_service.sh
sudo systemctl status led-matrix-cast
```

## Architecture

### Firmware Architecture (C++)
The firmware uses a dual-mode system:

**Mode System** (`src/main.cpp:9-27`):
- `MODE_SERIAL_STREAM` - Receives frames via serial
- `MODE_EFFECTS` - Runs built-in animations
- Switch modes via 's'/'e' commands over serial

**Core Classes**:
- `LEDMatrix` - Panel management, pixel mapping, FastLED interface
- `SerialStream` - 6Mbps frame protocol with start markers
- `Effects` - Built-in animation system with auto-cycling

**Serial Protocol**:
- Baud: 6,000,000 bps (upgraded from 2M)
- Frame format: `[0xFF, 0xFE, 0xFD]` + 3072 RGB bytes
- Connection handling: Auto-retry, device detection

### Python Utilities Architecture

**Core Infrastructure**:
- `serial_connection.py` - Robust connection management with auto-detection
- `stream_to_teensy.py` - Low-level frame streaming
- `led-matrix` - Unified command dispatcher (Python script)

**Visualization Modules**:
- `video_streamer.py` - Video/webcam with color correction
- `spectrogram.py` - Audio spectrum analyzer
- `vu_meter.py` - Stereo VU meter with multiple palettes
- `phase_meter.py` - Oscilloscope/Lissajous patterns
- `adsb_ticker/` - Aircraft tracking ticker display (see below)

**Web Interface System**:
- `api_server.py` - RESTful API for text display and controls
- `web_interface/` - Family-friendly message interface
- `home_assistant/` - HA integration and MQTT bridge

**Aircraft Ticker System** (`python_utils/adsb_ticker/`):
- `aircraft_data.py` - Fetch/parse aircraft data from tar1090/adsb.fi
- `ticker_renderer.py` - Render scrolling ticker with 5x8 font
- `flask_app.py` - Web preview interface with configuration
- `led_stream.py` - Bridge to stream ticker to LED matrix
- See `python_utils/adsb_ticker/README.md` for details

### Data Flow

1. **Streaming Mode**: Python → `serial_connection.py` → Teensy serial → `SerialStream` → `LEDMatrix`
2. **Effects Mode**: Teensy `Effects` system → `LEDMatrix`
3. **Web Interface**: Browser → REST API → Text renderer → Serial streaming
4. **Home Assistant**: HA → MQTT/REST → Text display → LED matrix
5. **Aircraft Ticker**: tar1090/adsb.fi → `AircraftDataSource` → `TickerRenderer` → LED matrix

## Hardware Configuration

- **Teensy 4.0** on pins 1-4 (bottom-left, bottom-right, top-left, top-right)
- **Panel wiring**: Vertical serpentine within each 8x32 panel
- **Power**: 5V up to 60A total (brightness limited to 96/255 default)
- **Serial**: USB, 6Mbps, auto-detection via device descriptors

## Common Development Patterns

### Adding New Visualizations
1. Create new Python script in `python_utils/`
2. Use `TeensyConnection` class for serial handling
3. Add command to `led-matrix` dispatcher
4. Frame format: 64x16 RGB, send via `write_frame()`

### Adding Firmware Effects
1. Inherit from `Effect` class in `Effects.h`
2. Implement `init()`, `update()`, `getName()` methods
3. Add to `effects[]` array in `main.cpp`

### Text Display System
- Font format: 5x8 bitmap arrays in `TextScroller`
- Add fonts to `font` dictionary in `text_scroller.py`
- REST API: `POST /api/text` with message, color, effect parameters
- Preset management: `GET/POST /api/text/presets`

### Home Assistant Integration
- REST commands for text display and control
- MQTT discovery for automatic entity creation
- Automations for time-based or event-triggered messages
- Configuration examples in `home_assistant/configuration.yaml`

### Working with Audio
- Use `sounddevice` library for input
- List devices: `./led-matrix vu --list-devices`
- Multiple sources: mic, system audio, device index

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Upload fails | Press button on Teensy during upload |
| Serial not found | Check `lsusb`, add user to dialout group |
| Web interface not loading | Check REST API server is running on correct port |
| HA integration not working | Verify MQTT broker settings and discovery enabled |
| Text not displaying | Check font exists, message length, brightness settings |
| Low frame rate | Reduce processing, check USB connection |
| Terminal freeze | Don't run `./led-matrix fireworks` directly; use timeout |
| Aircraft ticker no data | Check tar1090 URL, verify airspy.local is accessible |
| Aircraft ticker web 404 | Run `pip install flask pillow` in venv |

## Project Structure Notes

- **Virtual environment**: Always at `venv/` - all scripts expect this
- **Working directory**: All commands run from project root
- **Configuration**: Hardware config in `LEDMatrix::Config` struct
- **Dependencies**: Platform.io for firmware, requirements.txt for Python
- **Web service**: REST API server for text display and family interface
- **Home automation**: MQTT bridge and HA discovery configuration

## Current Implementation Status

### ✅ System Operational (Verified 2025-09-27)

**Recent Architecture**: Commit "30c367b Clean architecture" simplified the codebase while keeping all essential components.

**What Changed in Refactoring**:
- Simplified `serial_connection.py` to use only `TeensyConnection` + `DeviceLock`
- Removed `ProtocolV2Connection` from serial_connection.py imports
- Removed complex casting components (cast_server.py, chromecast_receiver.py, led_cast_server.py)
- **NOTE**: `ConfigManager`, `ResourceManager`, `PerformanceMonitor`, `MatrixState` files still exist and are still used by API server

**Verified Working Components**:
- ✅ Serial connection with Teensy at 6Mbps (`/dev/ttyACM0`)
- ✅ `DeviceLock` mechanism for exclusive device access
- ✅ `TeensyConnection` class with auto-detection and retry logic
- ✅ Text display command: `./led-matrix text "Hello World"`
- ✅ API server: `./led-matrix api` (serves on port 8080)
- ✅ Web interface with REST API and WebSocket status updates
- ✅ Test patterns: `./led-matrix test`

**Current Architecture**:
- **Core Serial**: `serial_connection.py` (TeensyConnection) + `device_lock.py` (file-based locking)
- **Configuration**: `config_manager.py` (JSON config files in `config/` directory)
- **State Management**: `matrix_state.py` (persists to `state/matrix_state.json`)
- **Performance**: `performance_monitor.py` (latency tracking, FPS monitoring)
- **Resources**: `resource_manager.py` (process tracking, resource cleanup)
- **API Server**: `api_server.py` with FastAPI, WebSocket status, SingletonLock
- **Visualizations**: Standalone Python scripts using TeensyConnection
- **Web UI**: Static HTML/CSS/JS in `web_interface/` served by API server

**Note About Blocking Commands**:
Visualization commands like `./led-matrix text` are **expected to block** - they run continuously until interrupted (Ctrl+C). This is normal behavior. Use `./led-matrix api` for non-blocking web interface access.

### State Management & Reconnection Testing (Verified 2025-09-27)

**Automated Tests** (`test_reconnection.py`):
- ✅ **Basic Connection**: Auto-detection, port enumeration, connection establishment
- ✅ **Mode Switching**: Seamless switching between streaming ('s') and effects ('e') modes
- ✅ **Reconnection**: Clean disconnect/reconnect cycles without state corruption
- ✅ **Device Lock**: File-based exclusive access prevents multi-process conflicts
  - First process acquires lock successfully
  - Second process correctly blocked while lock held
  - Lock properly released on connection close
  - Lock can be acquired by new process after release

**Manual USB Unplug/Replug Test** (Verified 2025-09-27):
- ✅ Device correctly detected as missing when unplugged
- ✅ Connection attempts properly fail when device is gone
- ✅ Device automatically re-detected after replug (appears as `/dev/ttyACM0`)
- ✅ Reconnection successful after replug
- ✅ Display functions normally after reconnection
- ⚠️ **Known Issue**: USB replug caused Claude CLI/Node.js/terminal crash during testing
  - This appears to be an issue with terminal/CLI serial monitoring, not the LED matrix code
  - The LED matrix code itself handles reconnection correctly
  - Recommend avoiding USB replug while CLI tools are actively monitoring serial

**State Persistence**:
- ✅ API state held in memory (via `matrix_state` singleton)
- ✅ State persists across API operations within same session
- ⚠️ **State file persistence**: `state/matrix_state.json` updates are triggered on shutdown/specific events
  - In-memory state always current and correct
  - Disk state may lag behind until explicit save
  - State is restored from memory on API server restart (if process stays alive)

**Serial Reconnection Behavior**:
- ✅ Automatic retry on connection failure (3 attempts by default)
- ✅ Port re-detection if device path changes
- ✅ Device lock prevents conflicts during reconnection
- ✅ Mode command sent after connection established
- ✅ Test frame sent to verify connection
- ✅ Graceful handling of device disappearance (no crashes in LED matrix code)