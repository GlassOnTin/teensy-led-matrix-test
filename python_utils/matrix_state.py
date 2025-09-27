#!/usr/bin/env python3
"""
Centralized state management for LED Matrix.
Provides thread-safe state operations with persistence and event system.
"""

import json
import time
import threading
from typing import Dict, Any, Optional, Callable, List
from pathlib import Path
from enum import Enum
from dataclasses import dataclass, asdict
try:
    from .config_manager import config_manager
    from .performance_monitor import performance_monitor
except ImportError:
    from config_manager import config_manager
    from performance_monitor import performance_monitor


class MatrixMode(Enum):
    """Matrix operating modes."""
    OFF = "off"
    EFFECTS = "effects"
    TEXT = "text"
    STREAMING = "streaming"
    VIDEO = "video"
    AUDIO = "audio"


@dataclass
class TextState:
    """State for text display."""
    message: str = ""
    color: str = "white"
    effect: str = "scroll"
    font: str = "medium"
    duration: float = 0  # 0 = indefinite
    position: str = "center"


@dataclass
class FrameStats:
    """Performance statistics."""
    fps: float = 0.0
    dropped_frames: int = 0
    total_frames: int = 0
    last_update: float = 0.0


class MatrixState:
    """
    Centralized state management for LED Matrix.
    Thread-safe with persistence and event system.
    """

    def __init__(self, state_file: str = None):
        """Initialize state manager."""
        if state_file is None:
            project_root = Path(__file__).parent.parent
            state_file = project_root / "state" / "matrix_state.json"

        self.state_file = Path(state_file)
        self._lock = threading.RLock()
        self._event_handlers: Dict[str, List[Callable]] = {}

        # Core state
        self._power = True
        self._brightness = config_manager.get('hardware', 'display.brightness_default', 96)
        self._mode = MatrixMode.EFFECTS
        self._active_effect = "rainbow"
        self._text_state = TextState()
        self._connections: Dict[str, Any] = {}
        self._frame_stats = FrameStats()

        # Load persistent state
        self.load_persistent()

    def _emit_event(self, event_type: str, data: Any = None):
        """Emit state change event to registered handlers."""
        handlers = self._event_handlers.get(event_type, [])
        for handler in handlers:
            try:
                handler(event_type, data)
            except Exception as e:
                print(f"Error in event handler: {e}")

    def on(self, event_type: str, handler: Callable):
        """Register event handler."""
        if event_type not in self._event_handlers:
            self._event_handlers[event_type] = []
        self._event_handlers[event_type].append(handler)

    def off(self, event_type: str, handler: Callable):
        """Unregister event handler."""
        if event_type in self._event_handlers:
            try:
                self._event_handlers[event_type].remove(handler)
            except ValueError:
                pass

    @property
    def power(self) -> bool:
        """Get power state."""
        with self._lock:
            return self._power

    @power.setter
    def power(self, value: bool):
        """Set power state."""
        with self._lock:
            if self._power != value:
                old_value = self._power
                self._power = value
                self._emit_event('power_changed', {'old': old_value, 'new': value})
                if value:
                    self._emit_event('power_on', value)
                else:
                    self._emit_event('power_off', value)

    @property
    def brightness(self) -> int:
        """Get brightness level (0-255)."""
        with self._lock:
            return self._brightness

    @brightness.setter
    def brightness(self, value: int):
        """Set brightness level (0-255)."""
        with self._lock:
            max_brightness = config_manager.get('hardware', 'display.brightness_max', 255)
            value = max(0, min(max_brightness, int(value)))
            if self._brightness != value:
                old_value = self._brightness
                self._brightness = value
                self._emit_event('brightness_changed', {'old': old_value, 'new': value})

    @property
    def mode(self) -> MatrixMode:
        """Get current operating mode."""
        with self._lock:
            return self._mode

    @mode.setter
    def mode(self, value: MatrixMode):
        """Set operating mode."""
        with self._lock:
            if isinstance(value, str):
                value = MatrixMode(value)
            if self._mode != value:
                old_value = self._mode
                self._mode = value
                self._emit_event('mode_changed', {'old': old_value.value, 'new': value.value})

    @property
    def active_effect(self) -> str:
        """Get active effect name."""
        with self._lock:
            return self._active_effect

    @active_effect.setter
    def active_effect(self, value: str):
        """Set active effect."""
        with self._lock:
            if self._active_effect != value:
                old_value = self._active_effect
                self._active_effect = value
                self._emit_event('effect_changed', {'old': old_value, 'new': value})

    @property
    def text_state(self) -> TextState:
        """Get text display state."""
        with self._lock:
            return self._text_state

    def update_text(self, **kwargs):
        """Update text state with keyword arguments."""
        with self._lock:
            old_state = asdict(self._text_state)
            for key, value in kwargs.items():
                if hasattr(self._text_state, key):
                    setattr(self._text_state, key, value)
            new_state = asdict(self._text_state)
            if old_state != new_state:
                self._emit_event('text_changed', {'old': old_state, 'new': new_state})

    @property
    def frame_stats(self) -> FrameStats:
        """Get frame statistics."""
        with self._lock:
            return self._frame_stats

    def update_frame_stats(self, fps: float = None, dropped: bool = False):
        """Update frame statistics with performance monitoring integration."""
        with self._lock:
            now = time.time()
            if fps is not None:
                self._frame_stats.fps = fps
                self._frame_stats.last_update = now
                # Record to performance monitor
                performance_monitor.record_metric('display_fps', fps)
            if dropped:
                self._frame_stats.dropped_frames += 1
                performance_monitor.record_metric('dropped_frames', 1)
            self._frame_stats.total_frames += 1
            performance_monitor.record_metric('total_frames', self._frame_stats.total_frames)

    def add_connection(self, conn_id: str, conn_info: Dict[str, Any]):
        """Add active connection."""
        with self._lock:
            self._connections[conn_id] = {
                **conn_info,
                'connected_at': time.time()
            }
            self._emit_event('connection_added', {'id': conn_id, 'info': conn_info})

    def remove_connection(self, conn_id: str):
        """Remove active connection."""
        with self._lock:
            if conn_id in self._connections:
                conn_info = self._connections.pop(conn_id)
                self._emit_event('connection_removed', {'id': conn_id, 'info': conn_info})

    def get_connections(self) -> Dict[str, Any]:
        """Get all active connections."""
        with self._lock:
            return self._connections.copy()

    def get_state_dict(self) -> Dict[str, Any]:
        """Get complete state as dictionary."""
        with self._lock:
            return {
                'power': self._power,
                'brightness': self._brightness,
                'mode': self._mode.value,
                'active_effect': self._active_effect,
                'text_state': asdict(self._text_state),
                'connections': self._connections,
                'frame_stats': asdict(self._frame_stats),
                'timestamp': time.time()
            }

    def update_from_dict(self, state_dict: Dict[str, Any]):
        """Update state from dictionary."""
        with self._lock:
            if 'power' in state_dict:
                self.power = state_dict['power']
            if 'brightness' in state_dict:
                self.brightness = state_dict['brightness']
            if 'mode' in state_dict:
                self.mode = MatrixMode(state_dict['mode'])
            if 'active_effect' in state_dict:
                self.active_effect = state_dict['active_effect']
            if 'text_state' in state_dict:
                text_data = state_dict['text_state']
                self._text_state = TextState(**text_data)

    def save_persistent(self) -> bool:
        """Save persistent state to file."""
        try:
            # Create directory if it doesn't exist
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # Only save persistent settings
            persistent_state = {
                'brightness': self._brightness,
                'mode': self._mode.value,
                'active_effect': self._active_effect,
                'text_state': asdict(self._text_state),
                'saved_at': time.time()
            }

            with open(self.state_file, 'w') as f:
                json.dump(persistent_state, f, indent=2)

            self._emit_event('state_saved', persistent_state)
            return True

        except Exception as e:
            print(f"Error saving state: {e}")
            return False

    def load_persistent(self) -> bool:
        """Load persistent state from file."""
        try:
            if not self.state_file.exists():
                return False

            with open(self.state_file, 'r') as f:
                saved_state = json.load(f)

            # Restore persistent settings
            with self._lock:
                if 'brightness' in saved_state:
                    self._brightness = saved_state['brightness']
                if 'mode' in saved_state:
                    try:
                        self._mode = MatrixMode(saved_state['mode'])
                    except ValueError:
                        self._mode = MatrixMode.EFFECTS
                if 'active_effect' in saved_state:
                    self._active_effect = saved_state['active_effect']
                if 'text_state' in saved_state:
                    self._text_state = TextState(**saved_state['text_state'])

            self._emit_event('state_loaded', saved_state)
            return True

        except Exception as e:
            print(f"Error loading state: {e}")
            return False

    def reset_to_defaults(self):
        """Reset state to default values."""
        with self._lock:
            display_config = config_manager.get_display_config()
            self._power = True
            self._brightness = display_config.get('brightness_default', 96)
            self._mode = MatrixMode.EFFECTS
            self._active_effect = "rainbow"
            self._text_state = TextState()
            self._connections.clear()
            self._frame_stats = FrameStats()
            self._emit_event('state_reset', self.get_state_dict())

    def validate_state(self) -> bool:
        """Validate current state values."""
        try:
            # Check brightness range
            max_brightness = config_manager.get('hardware', 'display.brightness_max', 255)
            if not (0 <= self._brightness <= max_brightness):
                return False

            # Check mode is valid
            if not isinstance(self._mode, MatrixMode):
                return False

            # Check text state
            if not isinstance(self._text_state, TextState):
                return False

            return True

        except Exception:
            return False


# Global instance
matrix_state = MatrixState()