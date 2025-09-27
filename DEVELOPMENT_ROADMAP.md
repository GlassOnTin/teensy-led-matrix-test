# LED Matrix Development Roadmap

## Project Vision
Transform the LED matrix from a collection of scripts into a robust, family-friendly message display system with Home Assistant integration.

## Current State Analysis

### Strengths
- Working hardware setup (Teensy 4.0 + 64x16 LED matrix)
- Functional firmware with dual-mode system
- Comprehensive visualization utilities
- Unified command-line interface (`led-matrix` script)
- Robust serial communication at 6Mbps

### Technical Debt
- Configuration scattered across multiple files with hardcoded values
- No centralized state management
- Complex casting system that's underutilized
- Basic error handling with limited recovery
- No proper resource lifecycle management
- Text system limited to single font/basic effects

## Architectural Foundation (Phase 1-2)

### 1. Configuration Management System
**Problem**: Settings hardcoded throughout codebase
**Solution**: Centralized configuration

```python
# config/hardware.json
{
  "display": {
    "width": 64,
    "height": 16,
    "panels": {
      "bottom_left": {"pin": 1},
      "bottom_right": {"pin": 2},
      "top_left": {"pin": 3},
      "top_right": {"pin": 4}
    },
    "brightness_default": 96,
    "brightness_max": 255,
    "skip_first_column": true
  },
  "serial": {
    "baud_rate": 6000000,
    "timeout": 2.0,
    "retry_attempts": 3
  }
}

# config/display.json
{
  "color_profiles": {
    "daylight": {"gamma": 1.4, "contrast": 1.3},
    "evening": {"gamma": 1.8, "contrast": 1.1},
    "night": {"gamma": 2.2, "contrast": 0.8}
  },
  "text_effects": {
    "scroll": {"speed_default": 30, "speed_range": [10, 100]},
    "fade": {"duration_default": 2.0},
    "bounce": {"amplitude": 3}
  }
}
```

**Implementation**:
- Create `config/` directory with JSON configs
- `ConfigManager` class with validation and defaults
- Runtime config updates via API
- Environment-specific configs (dev/prod)

### 2. Enhanced State Management
**Problem**: Implicit state scattered across modules
**Solution**: Centralized state store with persistence

```python
class MatrixState:
    def __init__(self):
        self.power = True
        self.brightness = 96
        self.current_mode = "effects"  # effects, text, streaming, off
        self.active_effect = "rainbow"
        self.last_text = {"message": "", "color": "white", "effect": "scroll"}
        self.connections = {}
        self.frame_stats = {"fps": 0, "dropped": 0}

    def save_persistent(self):
        """Save state that should persist across restarts"""

    def load_persistent(self):
        """Load saved state on startup"""
```

**Features**:
- State change events for logging/debugging
- Automatic persistence of user preferences
- State validation and rollback
- Thread-safe state updates

### 3. Robust Serial Protocol Enhancement
**Problem**: Basic protocol lacks error detection and feedback
**Solution**: Enhanced bidirectional protocol

```python
# Protocol v2.0 specification
class FrameV2:
    """
    Frame format:
    [SYNC: 0xFF, 0xFE, 0xFD] [VERSION: 0x02] [SEQ: 1 byte]
    [TYPE: 1 byte] [LENGTH: 2 bytes] [DATA: N bytes] [CRC: 2 bytes]
    """
    FRAME_SYNC = b'\xFF\xFE\xFD'
    VERSION = 0x02

    TYPE_DISPLAY_FRAME = 0x01
    TYPE_COMMAND = 0x02
    TYPE_STATUS_REQUEST = 0x03
    TYPE_STATUS_RESPONSE = 0x04
    TYPE_ACK = 0x05
    TYPE_ERROR = 0x06
```

**Features**:
- Frame sequence numbers for ordering
- CRC error detection
- Acknowledgment system
- Status reporting (temperature, fps, memory)
- Command protocol for mode switching
- Automatic retry with exponential backoff

### 4. Resource Management System
**Problem**: Memory leaks and orphaned processes
**Solution**: Proper lifecycle management

```python
class ResourceManager:
    """Manages frame buffers, processes, and connections"""

    def __init__(self):
        self.frame_pool = FrameBufferPool(size=10)
        self.active_processes = {}
        self.connection_pool = ConnectionPool(max_size=5)

    def cleanup_orphaned_processes(self):
        """Clean up Python scripts that failed to terminate"""

    def monitor_memory_usage(self):
        """Track and prevent memory leaks"""
```

## Family-Focused Features (Phase 3-4)

### 5. Enhanced Text Display System
**Current**: Single font, basic effects
**Target**: Rich text with multiple fonts and advanced effects

```python
class TextRenderer:
    """Advanced text rendering with multiple fonts and effects"""

    FONTS = {
        "small": "5x8_basic",
        "medium": "8x8_bold",
        "large": "8x16_display",
        "icons": "8x8_emoji"
    }

    EFFECTS = {
        "scroll": ScrollEffect,
        "fade": FadeEffect,
        "bounce": BounceEffect,
        "typewriter": TypewriterEffect,
        "rainbow": RainbowScrollEffect,
        "pulse": PulseEffect
    }
```

**Features**:
- Font upload system for custom fonts
- Effect chaining (fade in + scroll + fade out)
- Text positioning (left, center, right, custom)
- Multi-line text support
- Icon/emoji integration
- Real-time preview

### 6. Family Web Interface
**Target**: Simple, mobile-friendly message center

```html
<!-- Quick Access Panel -->
<div class="quick-messages">
  <button onclick="sendPreset('good_morning')">☀️ Good Morning</button>
  <button onclick="sendPreset('welcome_home')">🏠 Welcome Home</button>
  <button onclick="sendPreset('happy_birthday')">🎂 Happy Birthday</button>
  <button onclick="sendPreset('dinner_ready')">🍽️ Dinner Ready</button>
</div>

<!-- Custom Message -->
<div class="custom-message">
  <input type="text" id="message" placeholder="Type your message">
  <select id="font">
    <option value="small">Small Font</option>
    <option value="medium">Medium Font</option>
    <option value="large">Large Font</option>
  </select>
  <div class="color-picker">
    <button class="color red" onclick="setColor('red')"></button>
    <button class="color green" onclick="setColor('green')"></button>
    <button class="color blue" onclick="setColor('blue')"></button>
    <button class="color rainbow" onclick="setColor('rainbow')">🌈</button>
  </div>
  <button onclick="sendMessage()">Send Message</button>
</div>

<!-- Controls -->
<div class="controls">
  <button id="power-btn" onclick="togglePower()">Power Off</button>
  <label>Brightness: <input type="range" min="0" max="255" onchange="setBrightness(this.value)"></label>
</div>
```

### 7. RESTful API Design
**Endpoints for family interface and Home Assistant**

```python
# Text Display API
POST /api/text
{
  "message": "Hello World",
  "font": "medium",
  "color": "rainbow",
  "effect": "scroll",
  "duration": 10,
  "position": "center"
}

# Preset Management
GET    /api/presets              # List saved presets
POST   /api/presets              # Create new preset
PUT    /api/presets/{id}         # Update preset
DELETE /api/presets/{id}         # Delete preset

# Device Control
GET  /api/status                 # Get current state
POST /api/power                  # {"state": true/false}
POST /api/brightness             # {"level": 0-255}
POST /api/mode                   # {"mode": "text"|"effects"|"off"}

# Effects Control
GET  /api/effects                # List available effects
POST /api/effects/start          # {"effect": "rainbow", "duration": 60}
POST /api/effects/stop           # Stop current effect

# Font Management
GET  /api/fonts                  # List available fonts
POST /api/fonts/upload           # Upload custom font file
```

## Home Assistant Integration (Phase 5)

### 8. MQTT Bridge with Discovery
**Automatic Home Assistant entity creation**

```yaml
# Auto-discovered entities
light.led_matrix:
  brightness: 0-255
  effect_list: ["rainbow", "fire", "plasma", "starfield"]

text.led_matrix_message:
  min: 0
  max: 100

sensor.led_matrix_status:
  state: "on"|"off"|"text"|"effects"

switch.led_matrix_power:
  state: "on"|"off"
```

### 9. Home Assistant Automations
**Ready-to-use automation examples**

```yaml
# Morning greeting with weather
automation:
  - alias: "LED Matrix Morning Update"
    trigger:
      platform: time
      at: "07:00:00"
    condition:
      condition: state
      entity_id: binary_sensor.workday
      state: "on"
    action:
      service: text.set_value
      target:
        entity_id: text.led_matrix_message
      data:
        value: "Good Morning! {{ states('sensor.temperature') }}°C"

# Doorbell notification
automation:
  - alias: "LED Matrix Doorbell"
    trigger:
      platform: state
      entity_id: binary_sensor.doorbell
      to: "on"
    action:
      - service: light.turn_on
        target:
          entity_id: light.led_matrix
        data:
          effect: "bounce"
          brightness: 255
      - service: text.set_value
        target:
          entity_id: text.led_matrix_message
        data:
          value: "🚪 Someone at the door!"

# Bedtime mode
automation:
  - alias: "LED Matrix Bedtime"
    trigger:
      platform: time
      at: "22:00:00"
    action:
      service: light.turn_off
      target:
        entity_id: light.led_matrix
```

## Implementation Phases

### Phase 1: Foundation (Weeks 1-2)
1. **Configuration System**
   - Create `config/` directory structure
   - Implement `ConfigManager` class
   - Migrate hardcoded values to JSON configs
   - Add config validation and defaults

2. **State Management**
   - Implement `MatrixState` class
   - Add state persistence
   - Create state change event system
   - Thread-safe state operations

### Phase 2: Reliability (Weeks 3-4)
3. **Enhanced Serial Protocol**
   - Implement Protocol v2.0 with CRC
   - Add acknowledgment system
   - Bidirectional status reporting
   - Automatic retry logic

4. **Resource Management**
   - Memory pool for frame buffers
   - Process lifecycle management
   - Connection pooling
   - Automatic cleanup systems

### Phase 3: Core Features (Weeks 5-7)
5. **Text System Enhancement**
   - Multiple font support
   - Advanced effects library
   - Font upload system
   - Effect chaining

6. **REST API Server**
   - FastAPI implementation
   - Text display endpoints
   - Device control API
   - Preset management

### Phase 4: User Interface (Weeks 8-9)
7. **Family Web Interface**
   - Mobile-responsive design
   - Quick message presets
   - Real-time preview
   - Simple controls

8. **Remove Legacy Code**
   - Delete casting components
   - Cleanup unused files
   - Update documentation

### Phase 5: Home Automation (Weeks 10-11)
9. **MQTT Integration**
   - MQTT bridge implementation
   - Home Assistant discovery
   - Entity state synchronization

10. **HA Configuration**
    - Automation examples
    - Lovelace card configuration
    - Integration documentation

## Success Metrics

### Technical Metrics
- **Reliability**: 99.9% uptime, automatic recovery from failures
- **Performance**: Consistent 30+ FPS, <100ms API response times
- **Memory**: Stable memory usage, no leaks over 24h operation
- **Error Rate**: <0.1% frame drops, comprehensive error logging

### User Experience Metrics
- **Simplicity**: Non-technical family members can use interface
- **Response Time**: <2s from web button click to display update
- **Preset Usage**: Quick access to 10+ common messages
- **Integration**: Seamless HA automation triggers

## Technical Requirements

### Dependencies
```bash
# Python packages
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
paho-mqtt>=1.6.0
pydantic>=2.0.0
aiofiles>=23.0.0

# System requirements
python>=3.8
nodejs>=16 (for web interface build)
mosquitto (MQTT broker)
```

### Hardware Requirements
- Teensy 4.0 with USB connection
- 4x SK6812 LED panels (8x32 each)
- 5V power supply (minimum 20A for reasonable brightness)
- Network connection for web interface and HA integration

### File Structure
```
├── config/                    # Configuration files
│   ├── hardware.json
│   ├── display.json
│   └── presets.json
├── src/                       # Firmware (enhanced)
├── python_utils/              # Core utilities (refactored)
├── web_interface/             # New web interface
│   ├── api_server.py          # FastAPI server
│   ├── static/                # HTML/CSS/JS
│   └── templates/
├── home_assistant/            # HA integration
│   ├── mqtt_bridge.py
│   ├── configuration.yaml
│   └── automations.yaml
├── fonts/                     # Font collection
├── tests/                     # Unit and integration tests
└── docs/                      # Enhanced documentation
```

## Risk Mitigation

### Technical Risks
1. **Serial Communication Instability**
   - Mitigation: Enhanced protocol with retry logic
   - Fallback: Automatic reconnection and state recovery

2. **Memory Leaks in Long-Running Operation**
   - Mitigation: Resource pools and automatic cleanup
   - Monitoring: Memory usage tracking and alerts

3. **Home Assistant Integration Complexity**
   - Mitigation: Standard MQTT patterns and thorough testing
   - Fallback: REST API remains functional independently

### User Experience Risks
1. **Interface Too Complex for Family**
   - Mitigation: User testing with non-technical family members
   - Solution: Progressive disclosure, preset-first design

2. **Reliability Issues Causing Frustration**
   - Mitigation: Comprehensive error handling and recovery
   - Monitoring: Health checks and automatic restart capabilities

This roadmap provides a solid foundation for transforming the LED matrix into a reliable, family-friendly system while maintaining all current functionality during the transition.