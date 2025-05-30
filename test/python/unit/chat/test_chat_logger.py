"""
Legacy ChatLogger tests - DEPRECATED

The ChatLogger API has been updated to use storage backends.
See test_chat_logger_storage.py for the new tests.

This file is kept for compatibility but tests are skipped.
"""

import pytest


class TestChatLoggerLegacy:
    """Legacy ChatLogger tests - all skipped in favor of new storage backend tests."""
    
    @pytest.mark.skip(reason="ChatLogger API changed - see test_chat_logger_storage.py")
    def test_legacy_tests_deprecated(self):
        """All legacy tests are deprecated."""
        pass


# Import the new tests so they're discoverable
from .test_chat_logger_storage import *