"""
Configuration Loader
Loads and validates strategy configuration from YAML file
"""

import yaml
from pathlib import Path


class ConfigLoader:
    """Load configuration from YAML file"""
    
    def __init__(self, config_path='config/strategy_config.yaml'):
        self.config_path = Path(config_path)
        self.config = None
        
    def load(self):
        """Load configuration from YAML file"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        # Validate configuration
        self._validate_config()
        
        return self.config
    
    def _validate_config(self):
        """Validate required configuration keys"""
        required_keys = ['strategy', 'data', 'market', 'entry', 'exit', 
                        'position_sizing', 'risk_management', 'backtest']
        
        for key in required_keys:
            if key not in self.config:
                raise ValueError(f"Missing required configuration section: {key}")
    
    def get(self, key, default=None):
        """Get configuration value by key"""
        if self.config is None:
            self.load()
        
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def update(self, key, value):
        """Update configuration value"""
        if self.config is None:
            self.load()
        
        keys = key.split('.')
        config_ref = self.config
        
        for k in keys[:-1]:
            if k not in config_ref:
                config_ref[k] = {}
            config_ref = config_ref[k]
        
        config_ref[keys[-1]] = value
    
    def save(self, output_path=None):
        """Save configuration to file"""
        if output_path is None:
            output_path = self.config_path
        
        with open(output_path, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False, indent=2)

