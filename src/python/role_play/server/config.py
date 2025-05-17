"""
Configuration module for the FastAPI server
"""
import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
from typing import Dict, Any

class ServerConfig:
    """
    Server configuration class that handles loading environment variables
    and providing configuration values for the FastAPI server
    """
    def __init__(self):
        self.env_vars = self._load_env_variables()
        self.debug = self.env_vars.get('debug', False)
        self.environment = self.env_vars.get('environment', 'development')
        self.project_root = Path(self.env_vars.get('project_root', ''))
        
        # API keys
        self.openai_api_key = self.env_vars.get('openai_api_key')
        self.anthropic_api_key = self.env_vars.get('anthropic_api_key')
        self.google_api_key = self.env_vars.get('google_api_key')
        
        # Server settings
        self.host = self.env_vars.get('HOST', '0.0.0.0')
        self.port = int(self.env_vars.get('PORT', 8000))
        
        # Add version info
        self.version = '0.1.0'
        
    def _find_project_root(self) -> Path:
        """Find the project root directory"""
        # Start from the directory containing this file and move up
        current_path = Path(__file__).resolve()
        
        # Common project markers
        markers = ['.git', '.env', 'pyproject.toml', 'setup.py']
        
        for directory in [current_path, *current_path.parents]:
            if any((directory / marker).exists() for marker in markers):
                return directory
        
        # Use python-dotenv's built-in function as backup
        dotenv_path = find_dotenv(usecwd=True)
        if dotenv_path:
            return Path(dotenv_path).parent
            
        # Default to current working directory
        return Path.cwd()
        
    def _load_env_variables(self) -> Dict[str, Any]:
        """Load environment variables from .env file"""
        # Find project root
        project_root = self._find_project_root()
        env_path = project_root / '.env'
        
        # Try loading from project root
        loaded = load_dotenv(dotenv_path=env_path, override=True)
        
        # Fallback to find_dotenv
        if not loaded:
            loaded = load_dotenv(find_dotenv(usecwd=True), override=True)
        
        # Create dictionary of environment variables
        env_vars = {
            'openai_api_key': os.getenv('OPENAI_API_KEY'),
            'anthropic_api_key': os.getenv('ANTHROPIC_API_KEY'),
            'google_api_key': os.getenv('GOOGLE_API_KEY'),
            'debug': os.getenv('DEBUG', 'False').lower() == 'true',
            'environment': os.getenv('ENVIRONMENT', 'development'),
            'project_root': str(project_root),
            'HOST': os.getenv('HOST', '0.0.0.0'),
            'PORT': os.getenv('PORT', '8000')
        }
        
        return env_vars
    
    def validate_config(self) -> bool:
        """
        Validate essential configuration settings
        
        Returns:
            bool: True if configuration is valid, False otherwise
        """
        required_keys = []
        
        # Check if we're in dev mode - then we need these keys
        if self.environment == 'development':
            # In development, we need at least one LLM API key
            if not (self.openai_api_key or self.anthropic_api_key):
                print("⚠️ Warning: No LLM API keys found. At least one of OPENAI_API_KEY or ANTHROPIC_API_KEY is recommended.")
        
        # Check for required keys in all environments
        missing_keys = [key for key in required_keys if not getattr(self, key.lower(), None)]
        
        if missing_keys:
            print(f"❌ Missing required configuration: {', '.join(missing_keys)}")
            return False
            
        return True
    
    def get_api_info(self) -> Dict[str, bool]:
        """
        Get information about which APIs are configured
        
        Returns:
            Dict[str, bool]: Dictionary with API availability
        """
        return {
            'openai_available': bool(self.openai_api_key),
            'anthropic_available': bool(self.anthropic_api_key),
            'google_available': bool(self.google_api_key)
        }
    
    def __str__(self) -> str:
        """String representation of the configuration"""
        # Safely mask API keys
        masked_config = {}
        for key, value in self.env_vars.items():
            if key.endswith('_api_key') and value:
                masked_config[key] = f"{value[:4]}{'*' * (len(value) - 4)}"
            else:
                masked_config[key] = value
                
        # Format the output in a readable way
        lines = [
            f"Environment: {self.environment}",
            f"Debug mode: {self.debug}",
            f"Project root: {self.project_root}",
            f"Server: {self.host}:{self.port}",
            "API Keys:",
        ]
        
        for key in ['openai_api_key', 'anthropic_api_key', 'google_api_key']:
            display_key = key.replace('_', ' ').title()
            value = masked_config.get(key, 'Not set')
            lines.append(f"  - {display_key}: {value}")
            
        return "\n".join(lines)

# Create a singleton instance
config = ServerConfig()

if __name__ == "__main__":
    # Test the configuration
    print(config)
    if config.validate_config():
        print("✅ Configuration is valid")
    else:
        print("❌ Configuration is invalid")
