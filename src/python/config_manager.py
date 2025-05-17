import os
import sys
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

def find_project_root():
    """
    Find the project root directory using multiple strategies.
    
    Returns:
        Path: Path to the project root directory
    """
    # Strategy 1: Search for marker files/directories going up from the current file
    current_path = Path(__file__).resolve()
    
    # Look for common project markers like .git, .env, pyproject.toml, etc.
    markers = ['.git', '.env', 'pyproject.toml', 'setup.py', 'requirements.txt']
    
    # Start from the directory containing this file and move up
    for directory in [current_path, *current_path.parents]:
        # Check if any marker exists in this directory
        if any((directory / marker).exists() for marker in markers):
            return directory
    
    # Strategy 2: Use find_dotenv from python-dotenv
    dotenv_path = find_dotenv(usecwd=True)
    if dotenv_path:
        return Path(dotenv_path).parent
    
    # Strategy 3: Check for environment variable
    if 'PROJECT_ROOT' in os.environ:
        return Path(os.environ['PROJECT_ROOT'])
    
    # Fallback: Use the current working directory
    return Path.cwd()

def load_env_variables():
    """
    Load environment variables from .env file
    
    Returns:
        dict: Dictionary containing environment variables
    """
    # Find the project root
    project_root = find_project_root()
    env_path = project_root / '.env'
    
    # Print path for debugging
    print(f"Looking for .env at: {env_path}")
    
    # Try multiple loading strategies
    # First attempt to load from the found project root
    loaded = load_dotenv(dotenv_path=env_path, override=True)
    
    # If that fails, use find_dotenv to automatically locate the file
    if not loaded:
        loaded = load_dotenv(find_dotenv(usecwd=True), override=True)
        if loaded:
            env_path = Path(find_dotenv(usecwd=True))
            project_root = env_path.parent
    
    if loaded:
        print(f"✅ Environment variables loaded from {env_path}")
    else:
        print(f"⚠️ No .env file found. Using existing environment variables.")
    
    # Create a dictionary of relevant environment variables
    env_vars = {
        'openai_api_key': os.getenv('OPENAI_API_KEY'),
        'anthropic_api_key': os.getenv('ANTHROPIC_API_KEY'),
        'google_api_key': os.getenv('GOOGLE_API_KEY'),
        'debug': os.getenv('DEBUG', 'False').lower() == 'true',
        'environment': os.getenv('ENVIRONMENT', 'development'),
        'project_root': str(project_root)
    }
    
    return env_vars

def test_env_variables():
    """Test loading environment variables"""
    env_vars = load_env_variables()
    
    print("\nEnvironment Variables:")
    print(f"- Environment: {env_vars['environment']}")
    print(f"- Debug Mode: {env_vars['debug']}")
    print(f"- Project Root: {env_vars['project_root']}")
    
    # Safely print API keys (first 4 chars + ****)
    for key_name in ['openai_api_key', 'anthropic_api_key', 'google_api_key']:
        key_value = env_vars[key_name]
        if key_value:
            masked_key = key_value[:4] + '*' * (len(key_value) - 4)
            print(f"- {key_name.replace('_', ' ').title()}: {masked_key}")
        else:
            print(f"- {key_name.replace('_', ' ').title()}: Not set")

if __name__ == "__main__":
    test_env_variables()
