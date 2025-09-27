# Teensy LED Matrix Controller

A clean, powerful system for controlling a 64x16 LED matrix display using Teensy 4.0. Features video streaming, audio visualization, animations, web-based casting, and more.

## Quick Start

```bash
# 1. Setup (one time only)
./setup.sh

# 2. Upload firmware to Teensy
platformio run --target upload

# 3. Test it works
./led-matrix test --pattern

# 4. Have fun!
./led-matrix fireworks
```

## Features

- 🎬 **Video Playback** - Play any video file with color correction
- 🎵 **Audio Visualizer** - Real-time spectrum analyzer 
- 📺 **YouTube Streaming** - Direct streaming from YouTube
- 📝 **Text Display** - Scrolling messages with color effects
- 🎆 **Animations** - Fireworks, plasma, fire, matrix rain, and more
- 📷 **Webcam** - Live camera feed to LED display
- 🌐 **Web Casting** - Cast from any browser - screen, tabs, webcam, or files

## Usage Examples

```bash
# Play video on loop (flipped for ceiling mount)
./led-matrix video movie.mp4 --loop --flip

# Stream from YouTube  
./led-matrix youtube "https://youtube.com/watch?v=dQw4w9WgXcQ"

# Audio visualizer
./led-matrix audio

# Scrolling text
./led-matrix text "Hello World!"

# Built-in effects mode
./led-matrix effects

# 🌐 Web-based casting - stream from any device!
./led-matrix cast
# Then open http://localhost:8080 in any browser
```

## Hardware

- **Controller**: Teensy 4.0
- **Display**: 4x SK6812 LED panels (8x32 each) = 64x16 pixels total
- **Power**: 5V supply (recommended 60A for full brightness)
- **Wiring**: Connect panels to Teensy pins 1-4, share ground

### Panel Layout
```
[Pin 3: Top-Left   ][Pin 4: Top-Right  ]
[Pin 1: Bottom-Left][Pin 2: Bottom-Right]
```

## All Commands

Run `./led-matrix --help` to see all options:

| Command | Description |
|---------|-------------|
| `test` | Test serial connection and display patterns |
| `video <file>` | Play video file with effects |
| `youtube <url>` | Stream from YouTube |
| `audio` | Real-time audio spectrum analyzer |
| `text <message>` | Display scrolling text |
| `fireworks` | Animated fireworks display |
| `effects` | Switch to built-in effects |
| `webcam` | Stream from webcam |
| `cast` | Start web-based casting server |
| `cycle` | Auto-cycle through effects |
| `vu` | VU meter visualization |
| `phase` | Phase meter/oscilloscope |

## Development

### Project Structure
```
├── src/              # C++ firmware
├── python_utils/     # Python utilities
├── examples/         # Example code
├── led-matrix        # Main command-line tool
├── setup.sh          # Setup script
└── requirements.txt  # Python dependencies
```

### Building Firmware
```bash
platformio run                  # Compile
platformio run --target upload  # Upload
platformio device monitor       # Serial monitor
```

### Python API
```python
from python_utils.video_streamer import VideoStreamer

streamer = VideoStreamer()
streamer.process_video_opencv("video.mp4", loop=True)
```

## Troubleshooting

- **Upload fails**: Press the button on Teensy when prompted
- **Permission denied**: Run `sudo usermod -a -G dialout $USER` and logout/login
- **No audio device**: List devices with `./led-matrix audio --list-devices`
- **Low FPS**: Try reducing gamma correction or disabling effects

## License

This project uses the FastLED library. See LICENSE for details.