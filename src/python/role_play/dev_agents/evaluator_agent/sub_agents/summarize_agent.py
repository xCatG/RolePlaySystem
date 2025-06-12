"""Agent that synthesizes all analyses into the final review report."""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool

from .. import MODEL
from ..model import FinalReviewReport
from .. import tools as eval_tools


class SummarizeAgent(LlmAgent):
    def __init__(self, language: str, **kwargs):
        instruction = (
            "You are the lead evaluator combining feedback from multiple reviewers. "
            f"Write the final report in {language}. "
            "Return only the JSON for the FinalReviewReport schema."
        )
        super().__init__(
            name="summarize_agent",
            model=MODEL,
            instruction=instruction,
            tools=[FunctionTool(eval_tools.store_final_review)],
            **kwargs,
        )
