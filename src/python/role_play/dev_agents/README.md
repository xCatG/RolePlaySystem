# Roleplay Development Agents

This directory contains ADK agents designed for **local development and testing** using `adk web`.

## Purpose

The primary goal is to provide a simple environment to:

1.  Test and refine character system prompts.
2.  Explore available scenarios and characters.
3.  Experiment with ADK `Agent` configurations.

**This is NOT the production agent setup.** The production agent logic is managed via `src/python/role_play/chat/adk_client.py`, which *pulls configuration* from `agent.py` here.

## Quick Start

1.  **Set up environment**:
    ```bash
    # Ensure you're in the project's virtual environment
    # (e.g., source venv/bin/activate)

    # Set your Google AI API key (if not already set)
    export GOOGLE_AI_API_KEY="your-api-key-here"
    ```

2.  **Run `adk web`**:
    ```bash
    # Navigate to the parent directory
    cd src/python/role_play/dev_agents

    # Run adk web (ensure your venv python/adk is in PATH or use full path)
    adk web [--port=8001 override]
    ```

3.  **Use the agent**:
    * Open `http://localhost:8000` in your browser.
    * Select `roleplay_dev_agent` from the agent dropdown.
    * Try commands like:
        * `list_scenarios`
        * `list_characters medical_interview`
        * `get_character_prompt patient_chronic`
    * Use the prompts retrieved to manually test character responses.