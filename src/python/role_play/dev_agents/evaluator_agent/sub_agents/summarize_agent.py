# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Summarize the content of the FOMC meeting transcript."""

from google.adk.agents import Agent, LlmAgent

from .. import MODEL
from ..library.callback import rate_limit_callback
from ..model import FinalReviewReport


def create_summary_report_agent(language:str) -> Agent:
    instruction = f"""
You are an expert communications and soft skills coach, you are reviewing analysis for a chat session and giving a summary as a JSON object the following format

{FinalReviewReport.model_json_schema()}

Please make sure to return values of overall_assessment, key_strengths_demonstrated, key_areas_for_development, actionable_next_steps fields written in {language}.
    """

    return Agent(
        model=MODEL,
        name="summarize_report_agent",
        description="Summarize the area specific analysis reports into one coherent report.",
        instruction=instruction,
        output_schema=FinalReviewReport,
        output_key="final_report"
        #before_model_callback=rate_limit_callback,
    )