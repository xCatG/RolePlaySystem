"""
Evaluation agent for analyzing roleplay session transcripts and providing feedback.
"""
import os
import sys
from pathlib import Path
from typing import Dict, Optional, List, Any
from google.adk.agents import Agent
from google.adk.tools import FunctionTool

from . import MODEL
from .sub_agents.summarize_agent import SummarizeReportAgent
from .sub_agents.analysis_agent import AnalysisAgent

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "python"))


class EvaluatorAgent(Agent):
    """Agent for evaluating roleplay session transcripts."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)


evaluator_tools = []

# Create the evaluator agent
evaluator_agent = EvaluatorAgent(
    name="roleplay_evaluator",
    model=MODEL,
    description="Agent for evaluating roleplay session quality and providing feedback",
    instruction="""You are an expert roleplay evaluator. Your task is to analyze roleplay session transcripts and provide constructive feedback.

When evaluating a session, consider:

1. **Character Consistency**: Did the character maintain their personality, mannerisms, and role throughout?
2. **Engagement Quality**: Were the responses thoughtful, relevant, and engaging?
3. **Scenario Adherence**: Did the roleplay stay within the bounds of the given scenario?
4. **Language Use**: Was the language appropriate for the character and scenario?
5. **Immersion**: Did the character avoid breaking the fourth wall or mentioning they are an AI?

Provide both qualitative feedback and numerical scores. Be constructive and specific in your feedback.

When analyzing transcripts:
- Look for specific examples of good and poor roleplay
- Identify patterns in the conversation
- Note any moments where the character broke immersion
- Assess whether the participant's needs were met
- Consider the flow and pacing of the conversation

Your evaluation should help improve future roleplay sessions.""",
    sub_agents=[
        AnalysisAgent,
        SummarizeReportAgent
    ],
    tools=evaluator_tools
)

# Export the agent
agent = evaluator_agent


root_agent = agent


# --- Main block for verification ---
if __name__ == "__main__":
    print("Roleplay Evaluator Agent Module")
    print(f"Agent Name: {evaluator_agent.name}")
    print(f"Model: {MODEL}")
    print(f"Tools loaded: {len(evaluator_tools)}")
    
    print("\nEvaluation criteria:")
    print("- Character Consistency")
    print("- Engagement Quality")
    print("- Scenario Adherence")
    print("- Overall Quality")