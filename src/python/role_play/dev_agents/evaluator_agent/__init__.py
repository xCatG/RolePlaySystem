"""Evaluator agent module for roleplay session analysis."""
import os

MODEL = os.getenv("GOOGLE_GENAI_MODEL")
if not MODEL:
    MODEL = "gemini-2.5-flash-preview-05-20"  # Use a more capable model for evaluation
