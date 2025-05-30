"""Unit tests for ContentLoader."""
import json
import pytest
from pathlib import Path
from unittest.mock import mock_open, patch

from role_play.chat.content_loader import ContentLoader


class TestContentLoader:
    """Test cases for ContentLoader."""

    @pytest.fixture
    def sample_data(self):
        """Sample scenarios and characters data."""
        return {
            "scenarios": [
                {
                    "id": "medical_interview",
                    "name": "Medical Patient Interview",
                    "description": "Practice medical history taking",
                    "compatible_characters": ["patient_chronic", "patient_acute"]
                },
                {
                    "id": "customer_service",
                    "name": "Customer Service Interaction",
                    "description": "Handle customer complaints",
                    "compatible_characters": ["customer_angry", "customer_confused"]
                }
            ],
            "characters": [
                {
                    "id": "patient_chronic",
                    "name": "Sarah - Chronic Pain Patient",
                    "description": "Patient with chronic back pain"
                },
                {
                    "id": "patient_acute",
                    "name": "John - Acute Injury Patient",
                    "description": "Patient with recent sports injury"
                },
                {
                    "id": "customer_angry",
                    "name": "Karen - Angry Customer",
                    "description": "Upset about product quality"
                },
                {
                    "id": "customer_confused",
                    "name": "Bob - Confused Customer",
                    "description": "Doesn't understand how to use product"
                }
            ]
        }

    @pytest.fixture
    def content_loader(self):
        """Create ContentLoader instance."""
        return ContentLoader()

    def test_init_default_path(self):
        """Test ContentLoader initialization with default path."""
        loader = ContentLoader()
        assert loader.data_file == Path("data/scenarios.json")
        assert loader._data is None

    def test_init_custom_path(self):
        """Test ContentLoader initialization with custom path."""
        custom_path = "custom/path/data.json"
        loader = ContentLoader(custom_path)
        assert loader.data_file == Path(custom_path)
        assert loader._data is None

    def test_load_data_success(self, content_loader, sample_data):
        """Test successful data loading."""
        with patch("builtins.open", mock_open(read_data=json.dumps(sample_data))):
            data = content_loader.load_data()
            assert data == sample_data
            assert content_loader._data == sample_data

    def test_load_data_caching(self, content_loader, sample_data):
        """Test that data is cached after first load."""
        mock_file = mock_open(read_data=json.dumps(sample_data))
        with patch("builtins.open", mock_file):
            # First load
            data1 = content_loader.load_data()
            # Second load (should use cache)
            data2 = content_loader.load_data()
            
            assert data1 == data2
            # Open should only be called once due to caching
            mock_file.assert_called_once()

    def test_load_data_file_not_found(self, content_loader):
        """Test FileNotFoundError when data file doesn't exist."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            with pytest.raises(FileNotFoundError):
                content_loader.load_data()

    def test_load_data_invalid_json(self, content_loader):
        """Test JSONDecodeError when data file contains invalid JSON."""
        with patch("builtins.open", mock_open(read_data="invalid json")):
            with pytest.raises(json.JSONDecodeError):
                content_loader.load_data()

    def test_get_scenarios(self, content_loader, sample_data):
        """Test getting all scenarios."""
        with patch("builtins.open", mock_open(read_data=json.dumps(sample_data))):
            scenarios = content_loader.get_scenarios()
            assert scenarios == sample_data["scenarios"]
            assert len(scenarios) == 2

    def test_get_characters(self, content_loader, sample_data):
        """Test getting all characters."""
        with patch("builtins.open", mock_open(read_data=json.dumps(sample_data))):
            characters = content_loader.get_characters()
            assert characters == sample_data["characters"]
            assert len(characters) == 4

    def test_get_scenario_by_id_found(self, content_loader, sample_data):
        """Test getting scenario by ID when it exists."""
        with patch("builtins.open", mock_open(read_data=json.dumps(sample_data))):
            scenario = content_loader.get_scenario_by_id("medical_interview")
            assert scenario is not None
            assert scenario["id"] == "medical_interview"
            assert scenario["name"] == "Medical Patient Interview"

    def test_get_scenario_by_id_not_found(self, content_loader, sample_data):
        """Test getting scenario by ID when it doesn't exist."""
        with patch("builtins.open", mock_open(read_data=json.dumps(sample_data))):
            scenario = content_loader.get_scenario_by_id("nonexistent")
            assert scenario is None

    def test_get_character_by_id_found(self, content_loader, sample_data):
        """Test getting character by ID when it exists."""
        with patch("builtins.open", mock_open(read_data=json.dumps(sample_data))):
            character = content_loader.get_character_by_id("patient_chronic")
            assert character is not None
            assert character["id"] == "patient_chronic"
            assert character["name"] == "Sarah - Chronic Pain Patient"

    def test_get_character_by_id_not_found(self, content_loader, sample_data):
        """Test getting character by ID when it doesn't exist."""
        with patch("builtins.open", mock_open(read_data=json.dumps(sample_data))):
            character = content_loader.get_character_by_id("nonexistent")
            assert character is None

    def test_get_scenario_characters_success(self, content_loader, sample_data):
        """Test getting compatible characters for a scenario."""
        with patch("builtins.open", mock_open(read_data=json.dumps(sample_data))):
            characters = content_loader.get_scenario_characters("medical_interview")
            assert len(characters) == 2
            character_ids = [c["id"] for c in characters]
            assert "patient_chronic" in character_ids
            assert "patient_acute" in character_ids

    def test_get_scenario_characters_scenario_not_found(self, content_loader, sample_data):
        """Test getting characters for non-existent scenario."""
        with patch("builtins.open", mock_open(read_data=json.dumps(sample_data))):
            characters = content_loader.get_scenario_characters("nonexistent")
            assert characters == []

    def test_get_scenario_characters_no_compatible_field(self, content_loader):
        """Test getting characters when scenario has no compatible_characters field."""
        data = {
            "scenarios": [{"id": "test", "name": "Test Scenario"}],
            "characters": [{"id": "char1", "name": "Character 1"}]
        }
        with patch("builtins.open", mock_open(read_data=json.dumps(data))):
            characters = content_loader.get_scenario_characters("test")
            assert characters == []

    def test_empty_data_structure(self, content_loader):
        """Test handling empty scenarios and characters."""
        empty_data = {"scenarios": [], "characters": []}
        with patch("builtins.open", mock_open(read_data=json.dumps(empty_data))):
            assert content_loader.get_scenarios() == []
            assert content_loader.get_characters() == []
            assert content_loader.get_scenario_by_id("any") is None
            assert content_loader.get_character_by_id("any") is None

    # Language support tests
    @pytest.fixture
    def multilingual_data(self):
        """Sample data with multiple languages."""
        return {
            "scenarios": [
                {
                    "id": "medical_en",
                    "language": "en",
                    "name": "Medical Interview",
                    "description": "Practice medical history taking",
                    "compatible_characters": ["patient_en"]
                },
                {
                    "id": "medical_zh_tw",
                    "language": "zh-tw", 
                    "name": "醫療訪談",
                    "description": "練習醫療病史詢問",
                    "compatible_characters": ["patient_zh_tw"]
                },
                {
                    "id": "medical_ja",
                    "language": "ja",
                    "name": "医療面接",
                    "description": "医療履歴の聞き取り練習",
                    "compatible_characters": ["patient_ja"]
                }
            ],
            "characters": [
                {
                    "id": "patient_en",
                    "language": "en",
                    "name": "Sarah - Patient",
                    "description": "English speaking patient"
                },
                {
                    "id": "patient_zh_tw",
                    "language": "zh-tw",
                    "name": "李小姐 - 患者",
                    "description": "繁體中文患者"
                },
                {
                    "id": "patient_ja",
                    "language": "ja",
                    "name": "田中さん - 患者",
                    "description": "日本語を話す患者"
                }
            ]
        }

    def test_language_support_initialization(self):
        """Test ContentLoader initialization with supported languages."""
        loader = ContentLoader(supported_languages=["en", "zh-tw", "ja"])
        assert loader.supported_languages == ["en", "zh-tw", "ja"]
        
        # Test default language support
        loader_default = ContentLoader()
        assert loader_default.supported_languages == ["en"]

    def test_language_validation_success(self, multilingual_data):
        """Test successful language validation."""
        loader = ContentLoader(supported_languages=["en", "zh-tw", "ja"])
        with patch("builtins.open", mock_open(read_data=json.dumps(multilingual_data))):
            # Should not raise any exception
            data = loader.load_data()
            assert data == multilingual_data

    def test_language_validation_unsupported_scenario(self):
        """Test language validation failure for unsupported scenario language."""
        invalid_data = {
            "scenarios": [
                {
                    "id": "test_fr",
                    "language": "fr",  # Unsupported language
                    "name": "Test en français",
                    "description": "Test scenario"
                }
            ],
            "characters": []
        }
        loader = ContentLoader(supported_languages=["en", "zh-tw", "ja"])
        with patch("builtins.open", mock_open(read_data=json.dumps(invalid_data))):
            with pytest.raises(ValueError, match="Scenario 'test_fr' has unsupported language 'fr'"):
                loader.load_data()

    def test_language_validation_unsupported_character(self):
        """Test language validation failure for unsupported character language."""
        invalid_data = {
            "scenarios": [],
            "characters": [
                {
                    "id": "char_de",
                    "language": "de",  # Unsupported language
                    "name": "German Character",
                    "description": "German speaking character"
                }
            ]
        }
        loader = ContentLoader(supported_languages=["en", "zh-tw", "ja"])
        with patch("builtins.open", mock_open(read_data=json.dumps(invalid_data))):
            with pytest.raises(ValueError, match="Character 'char_de' has unsupported language 'de'"):
                loader.load_data()

    def test_language_defaults_to_en(self):
        """Test that missing language field defaults to 'en'."""
        data_no_lang = {
            "scenarios": [
                {
                    "id": "test",
                    "name": "Test Scenario",
                    "description": "No language field"
                }
            ],
            "characters": [
                {
                    "id": "char",
                    "name": "Test Character",
                    "description": "No language field"
                }
            ]
        }
        loader = ContentLoader(supported_languages=["en"])
        with patch("builtins.open", mock_open(read_data=json.dumps(data_no_lang))):
            # Should not raise exception as missing language defaults to "en"
            data = loader.load_data()
            assert data == data_no_lang

    def test_get_scenarios_by_language(self, multilingual_data):
        """Test filtering scenarios by language."""
        loader = ContentLoader(supported_languages=["en", "zh-tw", "ja"])
        with patch("builtins.open", mock_open(read_data=json.dumps(multilingual_data))):
            # Test English scenarios
            en_scenarios = loader.get_scenarios_by_language("en")
            assert len(en_scenarios) == 1
            assert en_scenarios[0]["id"] == "medical_en"
            
            # Test Traditional Chinese scenarios
            zh_tw_scenarios = loader.get_scenarios_by_language("zh-tw")
            assert len(zh_tw_scenarios) == 1
            assert zh_tw_scenarios[0]["id"] == "medical_zh_tw"
            
            # Test Japanese scenarios
            ja_scenarios = loader.get_scenarios_by_language("ja")
            assert len(ja_scenarios) == 1
            assert ja_scenarios[0]["id"] == "medical_ja"
            
            # Test non-existent language
            empty_scenarios = loader.get_scenarios_by_language("fr")
            assert empty_scenarios == []

    def test_get_characters_by_language(self, multilingual_data):
        """Test filtering characters by language."""
        loader = ContentLoader(supported_languages=["en", "zh-tw", "ja"])
        with patch("builtins.open", mock_open(read_data=json.dumps(multilingual_data))):
            # Test English characters
            en_characters = loader.get_characters_by_language("en")
            assert len(en_characters) == 1
            assert en_characters[0]["id"] == "patient_en"
            
            # Test Traditional Chinese characters
            zh_tw_characters = loader.get_characters_by_language("zh-tw")
            assert len(zh_tw_characters) == 1
            assert zh_tw_characters[0]["id"] == "patient_zh_tw"
            
            # Test Japanese characters
            ja_characters = loader.get_characters_by_language("ja")
            assert len(ja_characters) == 1
            assert ja_characters[0]["id"] == "patient_ja"

    def test_get_scenario_characters_by_language(self, multilingual_data):
        """Test getting scenario characters filtered by language."""
        loader = ContentLoader(supported_languages=["en", "zh-tw", "ja"])
        with patch("builtins.open", mock_open(read_data=json.dumps(multilingual_data))):
            # Test English scenario characters
            en_chars = loader.get_scenario_characters_by_language("medical_en", "en")
            assert len(en_chars) == 1
            assert en_chars[0]["id"] == "patient_en"
            
            # Test Traditional Chinese scenario characters
            zh_tw_chars = loader.get_scenario_characters_by_language("medical_zh_tw", "zh-tw")
            assert len(zh_tw_chars) == 1
            assert zh_tw_chars[0]["id"] == "patient_zh_tw"
            
            # Test non-existent scenario
            empty_chars = loader.get_scenario_characters_by_language("nonexistent", "en")
            assert empty_chars == []