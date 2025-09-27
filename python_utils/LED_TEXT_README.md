# LED Matrix Text Scroller

Colorful scrolling text display for the 64x16 LED matrix!

## Quick Start

```bash
# Simple message
./led_message "Happy Birthday!"

# Preset messages with effects
./led_message birthday    # Happy Birthday with rainbow & confetti
./led_message party       # Party Time with sparkles
./led_message welcome     # Welcome with gradient & stars
./led_message love        # I Love You with pulsing hearts
```

## Features

### Color Modes
- **rainbow** - Smooth rainbow gradient across text
- **fire** - Red/orange/yellow flame effect
- **ocean** - Blue/cyan ocean waves
- **pulse** - Pulsing brightness
- **sparkle** - Random white sparkles
- **gradient** - Color gradient from left to right
- **solid** - Single solid color

### Special Effects
- **confetti** - Random colored pixels falling
- **stars** - Twinkling stars in background
- **border** - Animated rainbow border
- **fade** - Fade edges for smooth appearance
- **none** - No extra effects

### Customization

```bash
# Custom text with options
./text_scroller.py "Your Message" \
    --color rainbow \
    --effect confetti \
    --speed 40 \
    --duration 30

# Slower scrolling for readability
./text_scroller.py "Important Notice" --speed 20

# Fast party mode
./text_scroller.py "PARTY!" --speed 60 --color sparkle --effect confetti
```

## Command Options

```
text_scroller.py [text] [options]

Options:
  --speed SPEED        Scroll speed in pixels/second (default: 30)
  --color MODE         Color mode (rainbow, fire, ocean, pulse, sparkle, gradient)
  --effect EFFECT      Special effect (none, confetti, stars, border, fade)
  --duration SECONDS   Run for specified time
  --preset PRESET      Use preset (birthday, welcome, party, love, congratulations)
  --test-mode         Run without hardware for testing
```

## Examples

### Birthday Celebration
```bash
./led_message birthday
# or custom:
./text_scroller.py "Happy 21st Birthday Sarah!" --color rainbow --effect confetti
```

### Welcome Sign
```bash
./led_message welcome
# or custom:
./text_scroller.py "Welcome Home!" --color gradient --effect stars --speed 25
```

### Party Mode
```bash
./led_message party
# or custom:
./text_scroller.py "DANCE FLOOR OPEN" --color sparkle --effect confetti --speed 50
```

### Romantic Message
```bash
./led_message love
# or custom:
./text_scroller.py "Will You Marry Me?" --color pulse --effect stars --speed 20
```

### Information Display
```bash
./text_scroller.py "Meeting at 3PM Room 201" --color solid --speed 25
```

## Character Support

The scroller supports:
- Uppercase letters (A-Z)
- Lowercase letters (a-z)
- Numbers (0-9)
- Common punctuation (. , ! ? : ; ' " - + = / \\ * # $ % & @ ^ _)
- Special symbols (♥ ♦ ♣ ♠ ★ ☺ ☻)
- Emoji (rendered as special characters)

## Tips

1. **Readability**: Use slower speeds (20-25) for important messages
2. **Party Effects**: Combine sparkle color with confetti for maximum fun
3. **Long Messages**: Text automatically loops when it scrolls off screen
4. **Brightness**: The fire and ocean modes are gentler on the eyes
5. **Testing**: Use `--test-mode` to preview without hardware

## Technical Details

- Runs at ~30 FPS for smooth scrolling
- 5x8 pixel font with 1 pixel spacing
- Automatic text wrapping and looping
- Serial communication at 2Mbps
- Y-axis inverted for proper display orientation
- Right-to-left scrolling direction

## Troubleshooting

- **Text upside down**: Fixed in current version
- **Text backwards**: Fixed in current version  
- **No display**: Check Teensy connection and serial port
- **Choppy scrolling**: Lower the speed or reduce effects
- **Text cut off**: Automatic - will loop back from the right

Enjoy your colorful LED messages! 🎉