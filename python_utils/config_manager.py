#!/usr/bin/env python3
"""
Configuration management system for LED Matrix.
Provides centralized configuration with validation and defaults.
"""

import json
import os
from typing import Dict, Any, Optional
from pathlib import Path


class ConfigManager:
    """Manages configuration files with validation and defaults."""

    def __init__(self, config_dir: str = None):
        """Initialize ConfigManager with configuration directory."""
        if config_dir is None:
            # Default to config/ in project root
            project_root = Path(__file__).parent.parent
            config_dir = project_root / "config"

        self.config_dir = Path(config_dir)
        self._configs = {}
        self._load_all_configs()

    def _load_all_configs(self):
        """Load all configuration files from the config directory."""
        config_files = ['hardware.json', 'display.json', 'presets.json']

        for config_file in config_files:
            config_path = self.config_dir / config_file
            if config_path.exists():
                config_name = config_file.replace('.json', '')
                self._configs[config_name] = self._load_config(config_path)
            else:
                print(f"Warning: Config file {config_file} not found")
                self._configs[config_file.replace('.json', '')] = {}

    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """Load a single configuration file with error handling."""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error parsing {config_path}: {e}")
            return {}
        except Exception as e:
            print(f"Error loading {config_path}: {e}")
            return {}

    def get(self, config_name: str, key_path: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Args:
            config_name: Name of config file (without .json)
            key_path: Dot-separated path to the value (e.g., 'display.width')
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        if config_name not in self._configs:
            return default

        value = self._configs[config_name]

        for key in key_path.split('.'):
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    def get_hardware(self) -> Dict[str, Any]:
        """Get hardware configuration."""
        return self._configs.get('hardware', {})

    def get_display(self) -> Dict[str, Any]:
        """Get display configuration."""
        return self._configs.get('display', {})

    def get_presets(self) -> Dict[str, Any]:
        """Get presets configuration."""
        return self._configs.get('presets', {})

    def get_serial_config(self) -> Dict[str, Any]:
        """Get serial communication configuration."""
        return self.get_hardware().get('serial', {
            'baud_rate': 6000000,
            'timeout': 2.0,
            'retry_attempts': 3
        })

    def get_display_config(self) -> Dict[str, Any]:
        """Get display hardware configuration."""
        return self.get_hardware().get('display', {
            'width': 64,
            'height': 16,
            'brightness_default': 96,
            'brightness_max': 255
        })

    def get_text_presets(self) -> Dict[str, Any]:
        """Get text message presets."""
        return self.get_presets().get('text_presets', {})

    def get_text_effects(self) -> Dict[str, Any]:
        """Get text effect configurations."""
        return self.get_display().get('text_effects', {})

    def get_color_profiles(self) -> Dict[str, Any]:
        """Get color profile configurations."""
        return self.get_display().get('color_profiles', {})

    def update_config(self, config_name: str, key_path: str, value: Any) -> bool:
        """
        Update configuration value and save to file.

        Args:
            config_name: Name of config file
            key_path: Dot-separated path to the value
            value: New value to set

        Returns:
            True if successful, False otherwise
        """
        if config_name not in self._configs:
            self._configs[config_name] = {}

        # Navigate to the parent of the target key
        config = self._configs[config_name]
        keys = key_path.split('.')

        for key in keys[:-1]:
            if key not in config:
                config[key] = {}
            config = config[key]

        # Set the value
        config[keys[-1]] = value

        # Save to file
        return self._save_config(config_name)

    def _save_config(self, config_name: str) -> bool:
        """Save configuration to file."""
        config_path = self.config_dir / f"{config_name}.json"

        try:
            # Ensure directory exists
            self.config_dir.mkdir(parents=True, exist_ok=True)

            with open(config_path, 'w') as f:
                json.dump(self._configs[config_name], f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving {config_path}: {e}")
            return False

    def validate_hardware_config(self) -> bool:
        """Validate hardware configuration."""
        hw_config = self.get_hardware()

        # Check required display settings
        display = hw_config.get('display', {})
        required_display = ['width', 'height', 'brightness_default', 'brightness_max']

        for key in required_display:
            if key not in display:
                print(f"Missing required display config: {key}")
                return False

        # Check serial settings
        serial = hw_config.get('serial', {})
        required_serial = ['baud_rate', 'timeout', 'retry_attempts']

        for key in required_serial:
            if key not in serial:
                print(f"Missing required serial config: {key}")
                return False

        # Validate ranges
        if not (1 <= display.get('brightness_default', 0) <= 255):
            print("Invalid brightness_default: must be 1-255")
            return False

        if not (1 <= display.get('brightness_max', 0) <= 255):
            print("Invalid brightness_max: must be 1-255")
            return False

        return True

    def get_preset_by_name(self, preset_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific text preset by name."""
        presets = self.get_text_presets()
        return presets.get(preset_name)

    def reload_configs(self):
        """Reload all configuration files from disk."""
        self._configs.clear()
        self._load_all_configs()


# Global instance for convenience
config_manager = ConfigManager()