# Simple agent for adk web testing
from google.adk.agents import Agent

# Simple roleplay agent for development/testing
root_agent = Agent(
    name="roleplay_dev_agent",
    model="gemini-2.0-flash",
    description="Development roleplay agent for testing character interactions",
    instruction="""You are a roleplay assistant. You can adopt different characters 
    and scenarios. Ask the user what character and scenario they'd like to explore, 
    then stay in character throughout the conversation.""",
    tools=[]  # Start simple, add tools as needed
)

agent = root_agent
