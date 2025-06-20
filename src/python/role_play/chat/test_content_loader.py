import unittest
from unittest.mock import patch, mock_open
import json
from typing import Dict, Any

from .content_loader import ContentLoader # Adjust import if necessary

# Mock JSON data as a string
MOCK_SCENARIOS_JSON_CONTENT = """
{
  "scenarios": [
    {
      "id": "test_scenario_1",
      "language": "en",
      "name": "Test Scenario 1 EN",
      "description": "English test scenario",
      "compatible_characters": ["char1_en"]
    },
    {
      "id": "test_scenario_zh",
      "language": "zh-TW",
      "name": "Test Scenario ZH",
      "description": "Chinese test scenario",
      "compatible_characters": ["char1_zh"]
    }
  ],
  "characters": [
    {
      "id": "char1_en",
      "language": "en",
      "name": "Test Character EN",
      "description": "English test character",
      "system_prompt": "Prompt EN"
    },
    {
      "id": "char1_zh",
      "language": "zh-TW",
      "name": "Test Character ZH",
      "description": "Chinese test character",
      "system_prompt": "Prompt ZH"
    }
  ],
  "scripts": [
    {
      "id": "script_en_1",
      "scenario_id": "test_scenario_1",
      "character_id": "char1_en",
      "language": "en",
      "goal": "English script goal 1",
      "script": [{"speaker": "participant", "line": "Hello"}]
    },
    {
      "id": "script_en_2",
      "scenario_id": "test_scenario_1",
      "character_id": "char1_en",
      "language": "en",
      "goal": "English script goal 2",
      "script": [{"speaker": "character", "line": "Hi"}]
    },
    {
      "id": "script_zh_tw",
      "scenario_id": "test_scenario_zh",
      "character_id": "char1_zh",
      "language": "zh_tw",
      "goal": "Chinese script goal (zh_tw)",
      "script": [{"speaker": "participant", "line": "你好"}]
    },
    {
      "id": "script_unsupported_lang",
      "scenario_id": "test_scenario_1",
      "character_id": "char1_en",
      "language": "xx",
      "goal": "Unsupported language script",
      "script": []
    }
  ]
}
"""

class TestContentLoader(unittest.TestCase):

    def _get_correct_load_resource_side_effect(self):
        full_data = json.loads(MOCK_SCENARIOS_JSON_CONTENT)

        def side_effect(resource_name):
            if resource_name == "scenarios.json":
                return full_data
            elif resource_name == "scenarios_en.json":
                return {
                    "scenarios": [s for s in full_data["scenarios"] if s.get("language") == "en"],
                    "characters": [c for c in full_data["characters"] if c.get("language") == "en"],
                    "scripts": [sc for sc in full_data["scripts"] if sc.get("language") == "en"],
                }
            elif resource_name == "scenarios_zh-TW.json":
                # ContentLoader normalizes zh_tw from file to zh-TW in memory
                return {
                    "scenarios": [s for s in full_data["scenarios"] if s.get("language") in ["zh-TW", "zh_tw"]],
                    "characters": [c for c in full_data["characters"] if c.get("language") in ["zh-TW", "zh_tw"]],
                    "scripts": [sc for sc in full_data["scripts"] if sc.get("language") in ["zh-TW", "zh_tw"]],
                }
            elif resource_name == "scenarios_xx.json": # For tests that might request this
                 return {
                    "scenarios": [], "characters": [], # Keep it simple for xx file
                    "scripts": [sc for sc in full_data["scripts"] if sc.get("language") == "xx"],
                }
            raise FileNotFoundError(f"Mocked _load_resource: {resource_name} not found by side_effect")
        return side_effect

    @patch.object(ContentLoader, '_load_resource')
    def test_load_data_loads_all_types(self, mock_load_resource):
        mock_load_resource.side_effect = self._get_correct_load_resource_side_effect()

        loader = ContentLoader(supported_languages=["en", "zh-TW"])
        # When load_data("en") is called:
        # 1. It tries scenarios_en.json -> mock returns filtered EN data.
        # 2. _normalize_language_codes is called on this EN data.
        # 3. _validate_languages is called on this EN data (should pass as no "xx" script).
        data_en = loader.load_data("en")
        self.assertTrue("scenarios" in data_en)
        self.assertTrue("characters" in data_en)
        self.assertTrue("scripts" in data_en)
        self.assertEqual(len(data_en["scenarios"]), 1)
        self.assertEqual(data_en["scenarios"][0]["id"], "test_scenario_1")
        self.assertEqual(len(data_en["characters"]), 1)
        self.assertEqual(data_en["characters"][0]["id"], "char1_en")
        self.assertEqual(len(data_en["scripts"]), 2) # script_en_1, script_en_2
        self.assertIsNotNone(next((s for s in data_en["scripts"] if s["id"] == "script_en_1"), None))

    @patch.object(ContentLoader, '_load_resource')
    def test_get_scripts_filters_by_language(self, mock_load_resource):
        mock_load_resource.side_effect = self._get_correct_load_resource_side_effect()
        loader = ContentLoader(supported_languages=["en", "zh-TW"])

        scripts_en = loader.get_scripts("en")
        self.assertEqual(len(scripts_en), 2)
        self.assertTrue(all(s["language"] == "en" for s in scripts_en))

        scripts_zh = loader.get_scripts("zh-TW")
        self.assertEqual(len(scripts_zh), 1) # Only script_zh_tw (normalized)
        self.assertEqual(scripts_zh[0]["id"], "script_zh_tw")
        self.assertEqual(scripts_zh[0]["language"], "zh-TW") # Check normalization

    @patch.object(ContentLoader, '_load_resource')
    def test_get_script_by_id(self, mock_load_resource):
        mock_load_resource.side_effect = self._get_correct_load_resource_side_effect()
        loader = ContentLoader(supported_languages=["en", "zh-TW"])

        script = loader.get_script_by_id("script_en_1", "en")
        self.assertIsNotNone(script)
        self.assertEqual(script["id"], "script_en_1")

        script_none = loader.get_script_by_id("non_existent_script", "en")
        self.assertIsNone(script_none)

        script_wrong_lang = loader.get_script_by_id("script_en_1", "zh-TW") # script_en_1 is not in zh-TW data
        self.assertIsNone(script_wrong_lang)

        script_zh = loader.get_script_by_id("script_zh_tw", "zh-TW")
        self.assertIsNotNone(script_zh)
        self.assertEqual(script_zh["id"], "script_zh_tw")

    @patch.object(ContentLoader, '_load_resource')
    def test_language_normalization_for_scripts(self, mock_load_resource):
        mock_load_resource.side_effect = self._get_correct_load_resource_side_effect()
        loader = ContentLoader(supported_languages=["en", "zh-TW"])

        # When load_data("zh-TW") is called:
        # 1. Tries scenarios_zh-TW.json -> mock returns data with "zh_tw" script.
        # 2. This data is then normalized by _normalize_language_codes.
        # 3. Then validated (should pass as "xx" script is not in this specific file's mock).
        data_zh = loader.load_data("zh-TW")

        self.assertEqual(len(data_zh["scripts"]), 1) # Only script_zh_tw
        script_zh_normalized = data_zh["scripts"][0] # It's the first and only one
        self.assertEqual(script_zh_normalized["id"], "script_zh_tw")
        self.assertEqual(script_zh_normalized["language"], "zh-TW") # Normalized

    @patch('importlib.resources.open_text')
    @patch('importlib.resources.files')
    def test_language_validation_for_scripts(self, mock_files, mock_open_text):
        mock_resource_file = mock_files.return_value.__truediv__.return_value
        mock_resource_file.open.return_value.__enter__.return_value.read.return_value = MOCK_SCENARIOS_JSON_CONTENT
        mock_open_text.return_value.__enter__.return_value.read.return_value = MOCK_SCENARIOS_JSON_CONTENT

        loader = ContentLoader(supported_languages=["en"]) # Only "en" is supported

        # Loading data for "en" should be fine, but it will filter out "script_unsupported_lang"
        # during the _filter_by_language step if its language is 'xx'.
        # The validation happens on the *original* language code *before* filtering if that language is requested
        # OR on the main data before filtering if a specific language file is not found.

        # To properly test validation, we need to ensure 'xx' is processed by _validate_languages
        # This happens when _load_resource loads the main file, then _normalize, then _validate
        # If we request 'en', the 'xx' script is filtered out by _filter_by_language before validation of the filtered set.
        # The validation in _validate_languages is called on the result of _filter_by_language.
        # However, the *main* data loaded by self._load_resource(self.resource_name) is normalized and then
        # immediately used to populate self._data[language] via _filter_by_language, and THEN _validate_languages
        # is called on that filtered data.

        # Let's adjust the test: try loading with 'xx' as a supported language temporarily for the loader
        # No, the validation logic in ContentLoader._validate_languages iterates through
        # data.get("scenarios", []), data.get("characters", []), data.get("scripts", [])
        # *after* filtering for a specific language.
        # So, if a script has 'xx', and we ask for 'en', it's filtered out and never validated.
        # If we ask for 'xx', and 'xx' is not in supported_languages for the loader,
        # it will try to load scenarios_xx.json, fail, then load main, then filter for 'xx' (empty), then validate (empty).

        # The current ContentLoader logic:
        # 1. load_data(language):
        # 2.   If language-specific file exists: load it, normalize, validate, return.
        # 3.   Else (or if 'en'):
        # 4.     Load main file (if not cached in self._data["main"])
        # 5.       Normalize main_raw_data -> self._data["main"]
        # 6.     Filter self._data["main"] by 'language' -> self._data[language]
        # 7.     Validate self._data[language] (the filtered data)
        #
        # This means a script with 'xx' in the main file will only cause validation error
        # if 'xx' is in `supported_languages` AND we request `language='xx'`.
        # Or, if a language-specific file `scenarios_xx.json` contains an item with language 'yy'
        # and 'yy' is not in `supported_languages`.

        # Test case: script with 'xx' language in main file, loader supports 'en' and 'xx'.
        # Requesting 'xx' should trigger validation on that 'xx' script.
        loader_supports_xx = ContentLoader(supported_languages=["en", "zh-TW", "xx"])
        with self.assertRaisesRegex(ValueError, "Script 'script_unsupported_lang' has unsupported language 'xx'"):
            # This will fail because loader_supports_xx *does* support 'xx'.
            # The error should be that 'xx' is not in the default supported_languages of a *new* loader.
            pass

        # Correct test for validation:
        # Load main data which contains 'script_unsupported_lang' with lang 'xx'.
        # The loader itself only supports 'en'.
    @patch.object(ContentLoader, '_load_resource')
    def test_language_validation_for_scripts(self, mock_load_resource_method):
        MOCK_SCENARIOS_YY_JSON_CONTENT_WITH_XX_SCRIPT = """
        {
          "scenarios": [], "characters": [],
          "scripts": [{
              "id": "script_in_yy_file_with_xx_lang",
              "scenario_id": "test_scenario_1",
              "character_id": "char1_en",
              "language": "xx",
              "goal": "Unsupported language script in YY file",
              "script": []
            }]
        }
        """
        yy_data_with_xx_script = json.loads(MOCK_SCENARIOS_YY_JSON_CONTENT_WITH_XX_SCRIPT)

        def load_resource_side_effect(resource_name):
            if resource_name == "scenarios_yy.json": # yy is requested
                return yy_data_with_xx_script
            # No scenarios.json needed if specific file is found and loaded successfully by _load_resource
            # and ContentLoader uses it without falling back.
            # ContentLoader will try to load language_specific_file first if language != "en".
            raise FileNotFoundError(f"Mocked FileNotFoundError for {resource_name} in this test, expected scenarios_yy.json")

        mock_load_resource_method.side_effect = load_resource_side_effect

        # Loader supports "yy" (the requested language for the file), but not "xx" (language of the script in the file)
        loader = ContentLoader(supported_languages=["en", "yy"])
        with self.assertRaisesRegex(ValueError, "Script 'script_in_yy_file_with_xx_lang' has unsupported language 'xx'"):
            loader.load_data("yy") # Request "yy". This will load scenarios_yy.json.


if __name__ == '__main__':
    unittest.main()
