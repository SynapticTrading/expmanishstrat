"""
Configuration Loader Module
Loads and validates strategy configuration from YAML file
"""

import yaml
import os
from pathlib import Path
from typing import Dict, Any


class ConfigLoader:
    """Load and manage strategy configuration"""

    def __init__(self, config_path: str = None):
        """
        Initialize config loader

        Args:
            config_path: Path to config YAML file
        """
        if config_path is None:
            # Default to config/strategy_config.yaml
            project_root = Path(__file__).parent.parent
            config_path = project_root / "config" / "strategy_config.yaml"

        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        with open(self.config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Validate required fields
        self._validate_config(config)

        return config

    def _validate_config(self, config: Dict[str, Any]):
        """Validate configuration has all required fields"""
        required_fields = [
            'strategy_name',
            'instrument',
            'expiry_type',
            'candle_timeframe',
            'entry_start_time',
            'entry_end_time',
            'initial_capital',
            'data_paths'
        ]

        for field in required_fields:
            if field not in config:
                raise ValueError(f"Missing required config field: {field}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key

        Args:
            key: Configuration key (supports nested keys with dot notation)
            default: Default value if key not found

        Returns:
            Configuration value
        """
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def get_data_path(self, data_type: str) -> Path:
        """
        Get absolute path to data file

        Args:
            data_type: Type of data (weekly_expiry, monthly_expiry, spot_price, india_vix)

        Returns:
            Absolute path to data file
        """
        relative_path = self.config['data_paths'].get(data_type)
        if relative_path is None:
            raise ValueError(f"Data path not found for: {data_type}")

        project_root = Path(__file__).parent.parent
        return project_root / relative_path

    def __getitem__(self, key: str) -> Any:
        """Allow dictionary-style access"""
        return self.get(key)

    def __repr__(self) -> str:
        return f"ConfigLoader(config_path='{self.config_path}')"


# Global config instance
_config_instance = None


def get_config(config_path: str = None) -> ConfigLoader:
    """
    Get global configuration instance (singleton pattern)

    Args:
        config_path: Path to config file (only used on first call)

    Returns:
        ConfigLoader instance
    """
    global _config_instance

    if _config_instance is None:
        _config_instance = ConfigLoader(config_path)

    return _config_instance
