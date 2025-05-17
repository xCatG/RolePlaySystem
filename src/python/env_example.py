from config_manager import load_env_variables
import anthropic
import openai
from pathlib import Path

def initialize_clients():
    """Initialize API clients using environment variables"""
    # Load environment variables
    env_vars = load_env_variables()
    
    # Initialize OpenAI client
    openai_client = None
    if env_vars['openai_api_key']:
        openai_client = openai.OpenAI(api_key=env_vars['openai_api_key'])
        print("✅ OpenAI client initialized")
    else:
        print("❌ OpenAI client not initialized (API key missing)")
    
    # Initialize Anthropic client
    anthropic_client = None
    if env_vars['anthropic_api_key']:
        anthropic_client = anthropic.Anthropic(api_key=env_vars['anthropic_api_key'])
        print("✅ Anthropic client initialized")
    else:
        print("❌ Anthropic client not initialized (API key missing)")
    
    # Return initialized clients
    return {
        'openai': openai_client,
        'anthropic': anthropic_client,
        'env': env_vars
    }

def main():
    """Main function that demonstrates how to use the environment variables"""
    print("Initializing API clients...\n")
    
    # Initialize clients using environment variables
    clients = initialize_clients()
    
    # Print environment info
    print(f"\nRunning in {clients['env']['environment']} environment")
    print(f"Debug mode: {'Enabled' if clients['env']['debug'] else 'Disabled'}")
    
    # Show project structure
    project_root = Path(__file__).parents[3]  # Go up 3 levels from this file
    print(f"\nProject root: {project_root}")
    print(f".env file location: {project_root / '.env'}")

if __name__ == "__main__":
    main()
