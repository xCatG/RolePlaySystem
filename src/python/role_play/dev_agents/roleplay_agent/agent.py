"""Simple ADK agent for roleplay testing."""
import json
from pathlib import Path
from google import adk

# Initialize ADK
adk.init()

@adk.root_agent
async def roleplay_agent():
    """Root agent for roleplay testing.
    
    This is a simple agent for testing roleplay conversations
    using the ADK web interface. It loads character prompts
    from the scenarios.json file and responds in character.
    """
    
    # Load scenarios data
    data_path = Path(__file__).parent.parent.parent.parent.parent / "data" / "scenarios.json"
    with open(data_path) as f:
        data = json.load(f)
    
    # For testing, use the first character as default
    character = data["characters"][0]  # Sarah - Chronic Pain Patient
    
    # Set up the agent with the character's system prompt
    await adk.say(f"Starting roleplay as: {character['name']}")
    await adk.say(f"Description: {character['description']}")
    await adk.say("---")
    
    # Configure the agent's behavior
    adk.config.system_prompt = character["system_prompt"]
    
    # Wait for user input and respond in character
    while True:
        user_message = await adk.get_input("You: ")
        
        # Generate response using the configured character
        response = await adk.generate(
            prompt=user_message,
            system_prompt=character["system_prompt"]
        )
        
        await adk.say(f"{character['name'].split(' - ')[0]}: {response}")

if __name__ == "__main__":
    # This allows running the agent directly
    import asyncio
    asyncio.run(roleplay_agent())