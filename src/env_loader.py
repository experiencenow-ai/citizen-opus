"""
Environment loader - automatically load .env file.
Import this at the start of any script that needs API keys.
"""
import os

def load_env():
    """Load environment variables from .env file in current or parent directory."""
    # Try current directory first
    env_paths = [
        '.env',
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'),
    ]
    
    for env_path in env_paths:
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        # Handle 'export KEY=VALUE' or 'KEY=VALUE'
                        if line.startswith('export '):
                            line = line[7:]
                        key, value = line.split('=', 1)
                        os.environ[key.strip()] = value.strip()
            return True
    return False

# Auto-load on import
load_env()
