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
        assert loader.data_file == Path("static_data/scenarios.json")
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