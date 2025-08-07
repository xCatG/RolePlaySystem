import sys
from google.adk.agents import Agent, LlmAgent
from pathlib import Path

from .. import MODEL
from ..library.callback import rate_limit_callback
from ..model import SpecializedAssessment

# Add project root to path; this will break if you run adk web from places OTHER than dev_agents dir
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "python"))

from role_play.chat.models import ChatInfo


def create_analysis_agent(analysis_area:str, chat_info=ChatInfo) -> Agent:
    instruction = f"""
    You are an expert communications and soft skills coach. 
    You are looking at the chat history between your trainee named "{chat_info.participant_name}" 
    and an actor playing the character {chat_info.char_info} 
    for scenario {chat_info.scenario_info.description}
    with the goal of {chat_info.goal}. 

    Here is the chat transcription in {chat_info.chat_language}, where participant is {chat_info.participant_name}: 
    {chat_info.transcript_text}

    Provide analysis for how {chat_info.participant_name} performed in the area of {analysis_area}. 
    Provide evidence such as quote from the conversation to support the evaluation; 
    For improvement areas give example in contrast to the quote, in the form of "can say ... instead of <quote from conversation>".

    respond in JSON format {SpecializedAssessment.model_json_schema()}
    use {chat_info.chat_session_id} as chat_session_id field in your response.

    where positive_points, improvement_areas, specific_suggestions SHOULD be written in {chat_info.chat_language},
    while other fields MUST be written in English only.    
            """
    return Agent(
        model=MODEL,
        name="chat_history_analysis",
        description=f"Analyze Chat History and provide feedback in area of {analysis_area}",
        instruction=instruction,
        output_schema=SpecializedAssessment,
        disallow_transfer_to_parent=True,
        disallow_transfer_to_peers=True,
        output_key=f"report_{analysis_area}"
        #before_model_callback=rate_limit_callback,
    )
