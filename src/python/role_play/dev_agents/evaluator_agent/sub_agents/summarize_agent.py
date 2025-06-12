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

from google.adk.agents import Agent

from .. import MODEL
from ..library.callback import rate_limit_callback
# from ..tools.store_state import store_state_tool
# from . import summarize_meeting_agent_prompt

PROMPT = """
You are a financial analyst experienced in understanding the meaning, sentiment
and sub-text of financial meeting transcripts. Below is the transcript
of the latest FOMC meeting press conference.

<TRANSCRIPT>
{artifact.transcript_fulltext}
</TRANSCRIPT>

Read this transcript and create a summary of the content and sentiment of this
meeting. Call the store_state tool with key 'meeting_summary' and the value as your
meeting summary. Tell the user what you are doing but do not output your summary
to the user.

Then call transfer_to_agent to transfer to research_agent.

"""
SummarizeReportAgent = Agent(
    name="summarize_report_agent",
    model=MODEL,
    description=(
        "Summarize the content and sentiment of the latest FOMC meeting."
    ),
    instruction=PROMPT,
    tools=[],
    before_model_callback=rate_limit_callback,
)