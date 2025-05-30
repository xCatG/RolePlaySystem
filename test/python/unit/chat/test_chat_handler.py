"""Unit tests for ChatHandler system prompt generation."""
import pytest
from unittest.mock import Mock, patch

from role_play.chat.handler import ChatHandler


class TestChatHandlerSystemPrompt:
    """Test cases for ChatHandler system prompt generation."""

    @pytest.fixture
    def chat_handler(self):
        """Create ChatHandler instance."""
        return ChatHandler()

    @pytest.fixture
    def sample_english_character(self):
        """Sample English character data."""
        return {
            "id": "patient_en",
            "language": "en",
            "name": "Sarah - Patient",
            "description": "English speaking patient",
            "system_prompt": "You are Sarah, a 65-year-old woman with chronic back pain. You're anxious about new symptoms and need reassurance."
        }

    @pytest.fixture
    def sample_chinese_character(self):
        """Sample Traditional Chinese character data."""
        return {
            "id": "patient_zh_tw", 
            "language": "zh-tw",
            "name": "李小姐 - 患者",
            "description": "繁體中文患者",
            "system_prompt": "你是李小姐，一位65歲患有慢性背痛的女性。你對新症狀感到焦慮，需要安慰。"
        }

    @pytest.fixture
    def sample_japanese_character(self):
        """Sample Japanese character data."""
        return {
            "id": "patient_ja",
            "language": "ja", 
            "name": "田中さん - 患者",
            "description": "日本語を話す患者",
            "system_prompt": "あなたは田中さん、65歳の慢性的な腰痛を持つ女性です。新しい症状に不安を感じており、安心感が必要です。"
        }

    @pytest.fixture
    def sample_scenario(self):
        """Sample scenario data."""
        return {
            "id": "medical_interview",
            "name": "Medical Patient Interview",
            "description": "Practice taking medical history from a patient"
        }

    def test_system_prompt_english_character(self, chat_handler, sample_english_character, sample_scenario):
        """Test system prompt generation for English character."""
        agent = chat_handler._create_roleplay_agent(sample_english_character, sample_scenario)
        
        # Check that agent was created
        assert agent is not None
        assert agent.name == "roleplay_patient_en_medical_interview"
        
        # Check system prompt contains English language instruction
        instruction = agent.instruction
        assert "You are Sarah, a 65-year-old woman with chronic back pain" in instruction
        assert "Practice taking medical history from a patient" in instruction
        assert "Respond in English language" in instruction
        assert "Stay fully in character" in instruction
        assert "Do NOT break character" in instruction

    def test_system_prompt_chinese_character(self, chat_handler, sample_chinese_character, sample_scenario):
        """Test system prompt generation for Traditional Chinese character."""
        agent = chat_handler._create_roleplay_agent(sample_chinese_character, sample_scenario)
        
        # Check that agent was created
        assert agent is not None
        assert agent.name == "roleplay_patient_zh_tw_medical_interview"
        
        # Check system prompt contains Traditional Chinese language instruction
        instruction = agent.instruction
        assert "你是李小姐，一位65歲患有慢性背痛的女性" in instruction
        assert "Practice taking medical history from a patient" in instruction
        assert "Respond in Traditional Chinese language" in instruction
        assert "Stay fully in character" in instruction

    def test_system_prompt_japanese_character(self, chat_handler, sample_japanese_character, sample_scenario):
        """Test system prompt generation for Japanese character."""
        agent = chat_handler._create_roleplay_agent(sample_japanese_character, sample_scenario)
        
        # Check that agent was created
        assert agent is not None
        assert agent.name == "roleplay_patient_ja_medical_interview"
        
        # Check system prompt contains Japanese language instruction
        instruction = agent.instruction
        assert "あなたは田中さん、65歳の慢性的な腰痛を持つ女性です" in instruction
        assert "Practice taking medical history from a patient" in instruction
        assert "Respond in Japanese language" in instruction
        assert "Stay fully in character" in instruction

    def test_system_prompt_character_without_language_defaults_to_english(self, chat_handler, sample_scenario):
        """Test system prompt generation for character without language field (defaults to English)."""
        character_no_lang = {
            "id": "patient_no_lang",
            "name": "Test Patient", 
            "description": "Patient without language field",
            "system_prompt": "You are a test patient."
        }
        
        agent = chat_handler._create_roleplay_agent(character_no_lang, sample_scenario)
        
        # Check that agent was created
        assert agent is not None
        
        # Check system prompt defaults to English
        instruction = agent.instruction
        assert "You are a test patient." in instruction
        assert "Respond in English language" in instruction

    def test_system_prompt_unsupported_language_defaults_to_english(self, chat_handler, sample_scenario):
        """Test system prompt generation for character with unsupported language (defaults to English)."""
        character_unsupported = {
            "id": "patient_fr",
            "language": "fr",  # Unsupported language
            "name": "Patient français",
            "description": "French speaking patient", 
            "system_prompt": "Vous êtes un patient français."
        }
        
        agent = chat_handler._create_roleplay_agent(character_unsupported, sample_scenario)
        
        # Check that agent was created
        assert agent is not None
        
        # Check system prompt defaults to English for unsupported language
        instruction = agent.instruction
        assert "Vous êtes un patient français." in instruction
        assert "Respond in English language" in instruction  # Should default to English

    def test_system_prompt_structure(self, chat_handler, sample_english_character, sample_scenario):
        """Test the overall structure of the generated system prompt."""
        agent = chat_handler._create_roleplay_agent(sample_english_character, sample_scenario)
        instruction = agent.instruction
        
        # Check that all required sections are present
        assert "**Current Scenario:**" in instruction
        assert "**Roleplay Instructions:**" in instruction
        
        # Check all roleplay instructions are present
        assert "Stay fully in character" in instruction
        assert "Do NOT break character or mention you are an AI" in instruction
        assert "Respond naturally based on your character's personality" in instruction
        assert "IMPORTANT: Respond in" in instruction  # Language instruction
        assert "Engage with the user's messages within the roleplay context" in instruction

    def test_system_prompt_with_missing_fields(self, chat_handler):
        """Test system prompt generation with minimal character and scenario data."""
        minimal_character = {"id": "min_char"}
        minimal_scenario = {"id": "min_scenario"}
        
        agent = chat_handler._create_roleplay_agent(minimal_character, minimal_scenario)
        
        # Should handle missing fields gracefully
        assert agent is not None
        instruction = agent.instruction
        assert "You are a helpful assistant." in instruction  # Default system prompt
        assert "No specific scenario description." in instruction  # Default scenario description
        assert "Respond in English language" in instruction  # Default language