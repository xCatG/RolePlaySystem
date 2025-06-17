"""
Evaluation agent for analyzing roleplay session transcripts and providing feedback.
"""
import os
import sys
from pathlib import Path
from typing import Dict, Optional, List, Any
from google.adk.agents import Agent, ParallelAgent, SequentialAgent
from google.adk.tools import FunctionTool

from . import MODEL
from .model import ChatInfo
from .sub_agents.analysis_agent import create_analysis_agent
from .sub_agents.summarize_agent import create_summary_report_agent

evaluator_tools = []

def create_evaluator_agent(language: str, chat_info: ChatInfo):
    analysis_areas = ["clarity", "empathy", "escalation"]
    analysis_agents = [create_analysis_agent(analysis_area=analysis_areas, chat_info=chat_info) for analysis_areas in analysis_areas]
    parallel = ParallelAgent(
        name="parallelize_specialized_analysis",
        description=f"Create analysis report for participant {chat_info.participant_name} in the areas of [{', '.join(analysis_areas)}] from chat history",
        sub_agents=analysis_agents
    )
    summarize_agent = create_summary_report_agent(language=chat_info.chat_language)

    return SequentialAgent(
        name="chat_evaluation_agent",
        sub_agents=[parallel, summarize_agent]
    )

# Export the agent
agent = create_evaluator_agent("English",
                               ChatInfo(chat_language="English", chat_session_id="chat_session_2025_06_16_16_46_00",
                                        scenario_info={
                "id": "123",
                "name": "Clinic visit",
                "description": "routine clinic visit",
                "compatible_character_count": 1
            }, char_info={
                "id":"111",
                "name": "Jane Smith",
                "description": "Female, 36 years old, with two dogs and three daughters, light drinker, non-smoker, eats veggies every day."
            }, goal= "understanding risk for pet sickness from stress", transcript_text="""
My Trainee: Hi How are you
Jane Smith: Hi Doctor I have a question for you about my pet cat. He kept biting his tail.
My Trainee: He might be under stress, let me check on him.
Jane Smith: (holds cat from carrier and hands to doctor)
My Trainee: ok let me take a look at him. Yes, the tail has lots of bite marks.
            """, participant_name="My Trainee"))

root_agent = agent


# --- Main block for verification ---
if __name__ == "__main__":
    print("Roleplay Evaluator Agent Module")
