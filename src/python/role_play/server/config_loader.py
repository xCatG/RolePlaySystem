"""
Unified configuration loader for the Role Play System.

This module provides environment-aware configuration loading with:
- YAML configuration files for different environments
- Environment variable substitution
- .env file support for secrets
- Fail-fast validation
"""

import os
import yaml
from enum import Enum
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv

from .config import ServerConfig, DevelopmentConfig, ProductionConfig


class Environment(Enum):
    """Supported environments."""
    DEV = "dev"
    BETA = "beta"
    PROD = "prod"


class ConfigLoader:
    """Environment-aware configuration loader with YAML and .env support."""
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize config loader.
        
        Args:
            config_dir: Directory containing config files. Defaults to project root/config
        """
        if config_dir is None:
            # Default to config directory in project root
            project_root = Path(__file__).parent.parent.parent.parent.parent
            config_dir = project_root / "config"
        
        self.config_dir = Path(config_dir)
        # Create config directory if it doesn't exist (for development)
        if not self.config_dir.exists():
            import warnings
            warnings.warn(
                f"Config directory '{self.config_dir}' does not exist. "
                "Configuration will fall back to code defaults.",
                UserWarning,
                stacklevel=2
            )
        self._loaded_config: Optional[ServerConfig] = None
    
    def load_environment_variables(self) -> None:
        """Load environment variables from .env file if it exists."""
        env_file = Path(".env")
        if env_file.exists():
            load_dotenv(env_file)
    
    def substitute_environment_variables(self, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Substitute environment variables in configuration dictionary.
        
        Supports ${VAR_NAME} and ${VAR_NAME:default_value} syntax.
        
        Args:
            config_dict: Configuration dictionary with potential env var references
            
        Returns:
            Dict with environment variables substituted
        """
        def substitute_value(value):
            if isinstance(value, str):
                # Simple ${VAR} substitution
                if value.startswith("${") and value.endswith("}"):
                    var_name = value[2:-1]
                    if ":" in var_name:
                        var_name, default = var_name.split(":", 1)
                        env_value = os.getenv(var_name, default)
                    else:
                        env_value = os.getenv(var_name)
                        if env_value is None:
                            raise ValueError(f"Required environment variable '{var_name}' not found")
                    
                    # Expand tilde (~) to home directory only for path variables
                    if env_value and env_value.startswith("~") and var_name.endswith("_PATH"):
                        env_value = os.path.expanduser(env_value)
                    
                    return env_value
                # String interpolation for embedded variables
                elif "${" in value:
                    result = value
                    import re
                    for match in re.finditer(r'\$\{([^}]+)\}', value):
                        var_expr = match.group(1)
                        if ":" in var_expr:
                            var_name, default = var_expr.split(":", 1)
                            env_value = os.getenv(var_name, default)
                        else:
                            env_value = os.getenv(var_expr)
                            if env_value is None:
                                raise ValueError(f"Required environment variable '{var_expr}' not found")
                        
                        # Expand tilde (~) to home directory only for path variables
                        if env_value and env_value.startswith("~") and var_name.endswith("_PATH"):
                            env_value = os.path.expanduser(env_value)
                        
                        result = result.replace(match.group(0), env_value)
                    return result
            elif isinstance(value, dict):
                return {k: substitute_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                # Filter out empty strings after substitution
                substituted_list = [substitute_value(item) for item in value]
                return [item for item in substituted_list if item != ""]
            
            return value
        
        return substitute_value(config_dict)
    
    def load_yaml_config(self, environment: Environment) -> Dict[str, Any]:
        """
        Load YAML configuration for specified environment.
        
        Args:
            environment: Environment enum value
            
        Returns:
            Configuration dictionary
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML is invalid
        """
        config_file = self.config_dir / f"{environment.value}.yaml"
        used_fallback = False
        
        if not config_file.exists():
            # Fall back to default config if environment-specific config doesn't exist
            config_file = self.config_dir / "default.yaml"
            used_fallback = True
            
            if not config_file.exists():
                # If no YAML config exists, warn and use code defaults
                import warnings
                warnings.warn(
                    f"No YAML configuration found for environment '{environment.value}' "
                    f"or default.yaml in {self.config_dir}. Using Pydantic defaults.",
                    UserWarning,
                    stacklevel=3
                )
                return {}
        
        if used_fallback:
            import warnings
            warnings.warn(
                f"Environment-specific config '{environment.value}.yaml' not found. "
                f"Using default.yaml fallback.",
                UserWarning,
                stacklevel=3
            )
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f) or {}
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {config_file}: {e}")
        
        # Substitute environment variables
        return self.substitute_environment_variables(config_dict)
    
    def get_config(self, environment: Optional[str] = None, force_reload: bool = False) -> ServerConfig:
        """
        Get configuration for specified environment.
        
        Args:
            environment: Environment name or None for auto-detection
            force_reload: Force reload even if already cached
            
        Returns:
            ServerConfig instance
            
        Raises:
            ValueError: If environment is not supported
        """
        if self._loaded_config is not None and not force_reload:
            return self._loaded_config
        
        # Load environment variables first
        self.load_environment_variables()
        
        # Determine and validate environment
        if environment is None:
            # Check CONFIG_FILE first, then ENV, then ENVIRONMENT, then default to dev
            config_file = os.getenv("CONFIG_FILE")
            if config_file:
                # Extract environment from config file path (e.g., /app/config/beta.yaml -> beta)
                import re
                match = re.search(r'/(\w+)\.yaml$', config_file)
                if match:
                    environment = match.group(1)
                else:
                    environment = "dev"
            else:
                environment = os.getenv("ENV", os.getenv("ENVIRONMENT", "dev"))
        
        try:
            env_enum = Environment(environment)
        except ValueError:
            supported_envs = [e.value for e in Environment]
            raise ValueError(f"Unsupported environment '{environment}'. Supported environments: {supported_envs}")
        
        # Load YAML config
        yaml_config = self.load_yaml_config(env_enum)
        
        # Create appropriate config class
        if env_enum == Environment.PROD:
            config = ProductionConfig(**yaml_config)
        else:
            # Use development config for both DEV and BETA
            config = DevelopmentConfig(**yaml_config)
        
        self._loaded_config = config
        return config


# Global config loader instance
_config_loader: Optional[ConfigLoader] = None


def get_config_loader() -> ConfigLoader:
    """Get the global config loader instance."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader


def get_config(environment: Optional[str] = None) -> ServerConfig:
    """
    Get configuration using the global config loader.
    
    Args:
        environment: Environment name or None for auto-detection
        
    Returns:
        ServerConfig instance
    """
    return get_config_loader().get_config(environment)


def reset_config():
    """Reset the global config loader (for testing)."""
    global _config_loader
    _config_loader = None