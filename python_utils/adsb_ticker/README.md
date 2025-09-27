# Aircraft Ticker Display for LED Matrix

A reusable Flask-based web interface and LED matrix streamer that displays real-time aircraft data from tar1090/adsb.fi sources on a scrolling ticker display optimized for 64x16 LED matrices.

## Features

- **Real-time aircraft tracking** - Fetches data from tar1090 or adsb.fi API
- **Distance-based sorting** - Shows closest aircraft first
- **Configurable filtering** - Filter by max distance, minimum altitude
- **Web preview interface** - Browser-based configuration and preview
- **Direct LED streaming** - Stream directly to Teensy LED matrix
- **Scrolling ticker display** - Optimized 5x8 font for 64x16 displays
- **Reusable architecture** - Can be used standalone or integrated

## Quick Start

### Stream to LED Matrix

```bash
# Basic usage (defaults to airspy.local tar1090 data)
./led-matrix aircraft

# Custom location and filtering
./led-matrix aircraft \
  --lat 52.2 \
  --lon -4.5 \
  --max-distance 50 \
  --min-altitude 1000 \
  --scroll-speed 2

# Adjust brightness
./led-matrix aircraft --brightness 0.3
```

### Web Preview Interface

```bash
# Start web server on port 5555
./led-matrix aircraft-web

# Then open browser to http://localhost:5555
```

The web interface provides:
- Live preview of the scrolling ticker
- Configuration controls for all parameters
- Aircraft list with statistics
- Real-time updates every 5 seconds

## Architecture

### Components

1. **aircraft_data.py** - Data fetcher and parser
   - Connects to tar1090/adsb.fi JSON endpoints
   - Calculates distances using haversine formula
   - Filters and sorts by distance
   - Returns structured Aircraft objects

2. **ticker_renderer.py** - Display renderer
   - Generates 64x16 RGB frames
   - Renders text with PIL using minimal font
   - Implements smooth horizontal scrolling
   - Formats aircraft data: callsign, distance, altitude, speed

3. **flask_app.py** - Web interface
   - Flask server with REST API
   - MJPEG streaming endpoint for preview
   - Configuration management
   - Statistics and aircraft list views

4. **led_stream.py** - LED matrix bridge
   - Connects renderer to Teensy serial
   - Frame rate management
   - Reconnection handling
   - Performance monitoring

### Data Flow

```
tar1090/adsb.fi → AircraftDataSource → TickerRenderer → LED Matrix
                         ↓
                    Flask Web API
                         ↓
                  Browser Preview
```

## Configuration

### Command-line Options

```bash
--source URL          # Data source URL (default: airspy.local tar1090)
--lat FLOAT          # Observer latitude (default: 52.2)
--lon FLOAT          # Observer longitude (default: -4.5)
--max-distance NM    # Maximum distance in nautical miles (default: 50)
--min-altitude FT    # Minimum altitude in feet (default: 1000)
--scroll-speed N     # Scroll speed 1-10 (default: 2)
--update-interval S  # Data refresh interval (default: 5.0 seconds)
--brightness 0-1     # LED brightness multiplier (default: 0.375)
```

### Web Interface Configuration

All parameters can be adjusted through the web interface at runtime:
- Source URL
- Observer position (lat/lon)
- Distance and altitude filters
- Scroll speed
- Update interval

## Data Sources

### tar1090 (Local)

```bash
./led-matrix aircraft --source http://airspy.local/tar1090/data/aircraft.json
```

Format: Standard tar1090 JSON with fields:
- `hex` - Mode-S hex code
- `flight` - Callsign
- `lat`, `lon` - Position
- `alt_baro` - Barometric altitude
- `gs` - Ground speed
- `track` - Heading
- `squawk` - Squawk code

### adsb.fi API

**Note**: adsb.fi public API has rate limits (1 req/sec) and requires feeder access for some endpoints.

```bash
# Geographic search (requires feeder account)
./led-matrix aircraft \
  --source "https://api.adsb.fi/v2/lat/52.2/lon/-4.5/dist/50"
```

See: https://github.com/adsbfi/opendata

## Display Format

Each aircraft shows on the ticker as:
```
1. CALLSIGN  DIST     ALT       SPEED  |  2. NEXT_AIRCRAFT ...
```

Example:
```
1. RYR69ME   34.7nm   36575ft   521kt  |  2. UAE2LK    43.2nm   35000ft   537kt
```

## Standalone Usage

The ticker can be used without the Teensy LED matrix:

### As Python Module

```python
from python_utils.adsb_ticker import AircraftDataSource, TickerRenderer

# Create data source
source = AircraftDataSource(
    source_url="http://airspy.local/tar1090/data/aircraft.json",
    observer_lat=52.2,
    observer_lon=-4.5
)

# Fetch aircraft
aircraft = source.fetch_aircraft(max_distance_nm=50, min_altitude=1000)

# Render frames
renderer = TickerRenderer(width=64, height=16, font_size=8)
frame = renderer.render_frame(aircraft, scroll_speed=2)

# frame is numpy array (16, 64, 3) RGB
```

### As Flask App

```python
from python_utils.adsb_ticker import app, init_app

init_app()
app.run(host='0.0.0.0', port=5555)
```

Then access:
- Main interface: http://localhost:5555/
- Frame image: http://localhost:5555/frame.png
- MJPEG stream: http://localhost:5555/stream.mjpeg
- Aircraft API: http://localhost:5555/api/aircraft
- Config API: http://localhost:5555/api/config

## API Endpoints

### GET /api/aircraft

Returns current aircraft list:

```json
{
  "count": 3,
  "aircraft": [
    {
      "hex": "4CA281",
      "callsign": "RYR69ME",
      "altitude": 36575,
      "ground_speed": 521.4,
      "distance_nm": 34.7,
      "track": 110.2
    }
  ]
}
```

### POST /api/config

Update configuration:

```json
{
  "observer_lat": 52.2,
  "observer_lon": -4.5,
  "max_distance_nm": 50,
  "min_altitude": 1000,
  "scroll_speed": 2
}
```

### GET /frame.png

Returns current frame as PNG image (64x16)

### GET /stream.mjpeg

Returns MJPEG stream for live preview

## Requirements

- Python 3.7+
- requests
- numpy
- Pillow
- flask

Install via:
```bash
pip install requests numpy pillow flask
```

## Credits

- Aircraft data from tar1090 and adsb.fi
- Inspired by tar1090 filtering logic
- Built for Teensy 4.0 LED Matrix project

## License

Part of the teensy-led-matrix-test project