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
import copy
import json

from google.adk.agents import Agent, LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.models import LlmRequest, LlmResponse
from google.genai import types

from .. import MODEL
from ..library.callback import rate_limit_callback
from ..model import FinalReviewReport, SpecializedAssessment, Score
from typing import Optional

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
        output_key="final_report",
        # before_model_callback=rate_limit_callback,
        after_model_callback=report_storage_callback,
        # after_agent_callback=after_agent_callback
    )

def report_storage_callback(
    callback_context: CallbackContext, llm_response: LlmResponse
) -> Optional[LlmResponse]:
    """
    store individual reports from the state into final report object?
    Also need to do majority voting on the individual scores
    """
    original_text = ""
    if (llm_response.content is not None) and (llm_response.content.parts is not None) and ( len(llm_response.content.parts) > 0):
        # now check if part 1 is text
        if (llm_response.content.parts[0].text is not None) and (len(llm_response.content.parts[0].text.strip()) > 0):
            original_text = llm_response.content.parts[0].text.strip()

    # nothing to modify
    if len(original_text) == 0:
        return None

    try:
        final_report = FinalReviewReport(**json.loads(original_text))
        final_report.overall_score = -1.0

        if (final_report.area_assessments is None) or (len(final_report.area_assessments) == 0):
            # need to grab the individual assessments and fill them in here
            print(f"No assessments found in final report, need to backfill from state")
            # TODO look in callback_context.state for all items key with report_* and convert them into SpecializedAssessment one by one

        # calculate score via majority voting; low means 1 out of 3 possible points, med means 2 out of 3, high means 3 out of 3
        # we loop through all reports and add up all the scores and divide by the total possible points then that's the overall score
        score_map = {Score.low: (1,3), Score.med: (2,3), Score.high: (3,3)}
        score_part = 0
        score_denominator = 0
        for report in final_report.area_assessments:
            p, d = score_map[report.score]
            score_part += p
            score_denominator += d

        final_report.overall_score = score_part / score_denominator

        updated_final_report = final_report.model_dump_json()
        modified_parts = [copy.deepcopy(part) for part in llm_response.content.parts]
        modified_parts[0].text = updated_final_report

        new_response = LlmResponse(
            content=types.Content(role="model", parts=modified_parts),
            # copy other parts if necessary
        )
        return new_response
    except Exception as e:
        # swallow all exceptions and don't modify output
        return None
