"""Integration tests for script support in chat module."""
import pytest
from role_play.chat.content_loader import ContentLoader


class TestScriptIntegration:
    """Test script support integration with real resource files."""
    
    @pytest.fixture
    def content_loader(self):
        """Create a real ContentLoader."""
        return ContentLoader(supported_languages=["en", "zh-TW"])
    
    def test_load_english_scripts(self, content_loader):
        """Test loading English scripts from scenarios.json."""
        scripts = content_loader.get_scripts("en")
        assert len(scripts) == 2
        
        # Check first script
        script1 = scripts[0]
        assert script1["id"] == "medical_acute_frustration_simple"
        assert script1["scenario_id"] == "medical_interview"
        assert script1["character_id"] == "patient_acute"
        assert script1["language"] == "en"
        assert script1["goal"] == "Practice handling a patient who is downplaying their pain."
        assert len(script1["script"]) == 4
        assert script1["script"][-1] == {"speaker": "llm", "action": "stop"}
        
    def test_load_chinese_scripts(self, content_loader):
        """Test loading Traditional Chinese scripts from scenarios_zh-TW.json."""
        scripts = content_loader.get_scripts("zh-TW")
        assert len(scripts) == 2
        
        # Check first script
        script1 = scripts[0]
        assert script1["id"] == "medical_acute_frustration_simple_zh_tw"
        assert script1["scenario_id"] == "medical_interview_zh_tw"
        assert script1["character_id"] == "patient_acute_zh_tw"
        assert script1["language"] == "zh-TW"
        assert script1["goal"] == "練習處理淡化疼痛程度的病患"
        assert len(script1["script"]) == 4
        assert script1["script"][-1] == {"speaker": "llm", "action": "stop"}
        
    def test_get_script_by_id(self, content_loader):
        """Test retrieving specific scripts by ID."""
        # English script
        en_script = content_loader.get_script_by_id("medical_acute_frustration_simple", "en")
        assert en_script is not None
        assert en_script["id"] == "medical_acute_frustration_simple"
        
        # Chinese script
        zh_script = content_loader.get_script_by_id("customer_angry_refund_basic_zh_tw", "zh-TW")
        assert zh_script is not None
        assert zh_script["id"] == "customer_angry_refund_basic_zh_tw"
        
        # Non-existent script
        no_script = content_loader.get_script_by_id("nonexistent", "en")
        assert no_script is None
        
    def test_script_scenario_character_compatibility(self, content_loader):
        """Test that scripts reference valid scenarios and characters."""
        # English
        en_scripts = content_loader.get_scripts("en")
        en_scenarios = {s["id"] for s in content_loader.get_scenarios("en")}
        en_characters = {c["id"] for c in content_loader.get_characters("en")}
        
        for script in en_scripts:
            assert script["scenario_id"] in en_scenarios
            assert script["character_id"] in en_characters
            
        # Chinese
        zh_scripts = content_loader.get_scripts("zh-TW")
        zh_scenarios = {s["id"] for s in content_loader.get_scenarios("zh-TW")}
        zh_characters = {c["id"] for c in content_loader.get_characters("zh-TW")}
        
        for script in zh_scripts:
            assert script["scenario_id"] in zh_scenarios
            assert script["character_id"] in zh_characters
            
    def test_script_structure_validation(self, content_loader):
        """Test that all scripts have valid structure."""
        for lang in ["en", "zh-TW"]:
            scripts = content_loader.get_scripts(lang)
            for script in scripts:
                # Required fields
                assert "id" in script
                assert "scenario_id" in script
                assert "character_id" in script
                assert "language" in script
                assert "goal" in script
                assert "script" in script
                
                # Script array validation
                assert isinstance(script["script"], list)
                assert len(script["script"]) > 0
                
                # Last entry should be stop action
                last_entry = script["script"][-1]
                assert last_entry.get("speaker") == "llm"
                assert last_entry.get("action") == "stop"
                
                # Other entries should have speaker and line
                for entry in script["script"][:-1]:
                    assert "speaker" in entry
                    assert entry["speaker"] in ["character", "participant"]
                    assert "line" in entry
                    assert isinstance(entry["line"], str)
                    assert len(entry["line"]) > 0