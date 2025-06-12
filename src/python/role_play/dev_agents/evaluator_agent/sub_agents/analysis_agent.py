"""Generic analysis agent for evaluating a specific skill."""

from typing import Optional

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from .. import MODEL
from ..model import SpecializedAssessment
from .. import tools as eval_tools


class AnalysisAgent(LlmAgent):
    """Sub-agent that analyzes one area of the chat history."""

    def __init__(self, assessment_area: str, language: str, **kwargs):
        instruction = (
            "You are an expert coach evaluating a role play chat session. "
            f"Focus on {assessment_area}. Provide feedback in {language}. "
            "Return your analysis strictly in JSON format following the provided schema."
        )
        tools = [
            FunctionTool(eval_tools.get_chat_history),
            FunctionTool(eval_tools.get_scenario_details),
            FunctionTool(eval_tools.get_user_past_summaries),
        ]
        super().__init__(
            name=f"analysis_{assessment_area}",
            model=MODEL,
            instruction=instruction,
            tools=tools,
            **kwargs,
        )
        # Store custom attributes using object.__setattr__ to bypass pydantic restrictions
        object.__setattr__(self, "assessment_area", assessment_area)
        object.__setattr__(self, "language", language)
