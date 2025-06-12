"""Coordinator agent for multi-agent evaluation."""

from __future__ import annotations

from google.adk.agents import SequentialAgent, ParallelAgent

from . import MODEL
from .model import FinalReviewReport
from .sub_agents.analysis_agent import AnalysisAgent
from .sub_agents.summarize_agent import SummarizeAgent


DEFAULT_SKILLS = ["clarity", "empathy", "escalation"]


def create_evaluator_agent(language: str, skills: list[str] | None = None):
    skills = skills or DEFAULT_SKILLS
    analysis_agents = [AnalysisAgent(skill, language) for skill in skills]
    parallel = ParallelAgent(name="analysis_fanout", sub_agents=analysis_agents)
    summarizer = SummarizeAgent(language)
    return SequentialAgent(
        name="evaluator_agent",
        sub_agents=[parallel, summarizer],
    )


# Default instance for adk web
agent = create_evaluator_agent("English")
root_agent = agent
