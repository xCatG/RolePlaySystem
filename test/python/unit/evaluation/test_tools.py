"""Unit tests for evaluator agent tools."""

import json
import asyncio
from pathlib import Path
import sys
import pytest

sys.path.append(str(Path(__file__).parent.parent.parent))
from fixtures.helpers import MockStorageBackend

from role_play.chat.chat_logger import ChatLogger
from role_play.dev_agents.evaluator_agent import tools


class TestEvaluatorTools:
    @pytest.mark.asyncio
    async def test_get_scenario_details_multi_language(self):
        scenario_en = await tools.get_scenario_details("medical_interview", "en")
        scenario_zh = await tools.get_scenario_details("medical_interview_zh_tw", "zh-TW")
        assert scenario_en["name"] == "Medical Patient Interview"
        assert scenario_zh["language"] == "zh-TW"

    @pytest.mark.asyncio
    async def test_store_and_load_review(self):
        storage = MockStorageBackend()
        logger = ChatLogger(storage)
        tools.configure_tools(chat_logger=logger, storage=storage, user_id="u1")
        await tools.store_final_review("u1", "s1", {"a": 1})
        summaries = await tools.get_user_past_summaries("u1")
        assert summaries == [{"a": 1}]
