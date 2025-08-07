#!/usr/bin/env python3
"""Get the storage path from the dev config file."""

import os
import sys
import yaml
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_storage_path():
    """Extract and resolve the storage path from dev config."""
    config_file = 'config/dev.yaml'
    
    try:
        with open(config_file) as f:
            config = yaml.safe_load(f)
        
        # Get the base_dir from storage config
        path = config.get('storage', {}).get('base_dir', './data')
        
        # Handle environment variable substitution
        if '${' in path:
            # Extract the environment variable pattern
            # Format: ${STORAGE_PATH:./data} or ${STORAGE_PATH}
            if ':' in path:
                # Has default value
                default = path.split(':')[-1].rstrip('}')
                path = os.getenv('STORAGE_PATH', default)
            else:
                # No default value
                var_name = path.strip('${}')
                path = os.getenv(var_name, './data')
        
        # Expand tilde if present
        if path.startswith('~'):
            path = os.path.expanduser(path)
        
        # Make it absolute
        if not os.path.isabs(path):
            path = os.path.abspath(path)
            
        return path
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return './data'

if __name__ == '__main__':
    print(get_storage_path())