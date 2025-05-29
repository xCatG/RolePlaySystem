"""Tests for time utilities."""

import pytest
from datetime import datetime, timezone
from role_play.common.time_utils import (
    utc_now,
    utc_now_isoformat,
    parse_utc_datetime,
    is_valid_utc_isoformat,
)


class TestUtcNow:
    """Tests for utc_now function."""

    def test_returns_timezone_aware_datetime(self):
        """Test that utc_now returns a timezone-aware datetime."""
        dt = utc_now()
        assert dt.tzinfo is timezone.utc
        assert isinstance(dt, datetime)

    def test_returns_current_time(self):
        """Test that utc_now returns current time (within reasonable margin)."""
        before = datetime.now(timezone.utc)
        dt = utc_now()
        after = datetime.now(timezone.utc)
        
        # Should be within 1 second
        assert before <= dt <= after


class TestUtcNowIsoformat:
    """Tests for utc_now_isoformat function."""

    def test_default_format_with_zulu(self):
        """Test default format returns Z suffix."""
        iso_str = utc_now_isoformat()
        assert iso_str.endswith('Z')
        assert 'T' in iso_str
        assert '+' not in iso_str
        assert '.' in iso_str  # microseconds by default

    def test_format_without_zulu(self):
        """Test format without Z suffix."""
        iso_str = utc_now_isoformat(zulu=False)
        assert iso_str.endswith('+00:00')
        assert 'T' in iso_str

    def test_format_without_microseconds(self):
        """Test format without microseconds."""
        iso_str = utc_now_isoformat(microseconds=False)
        assert iso_str.endswith('Z')
        assert '.' not in iso_str.replace('.', '', 1)  # No additional dots after removing first one

    def test_format_combinations(self):
        """Test various format combinations."""
        # No zulu, no microseconds
        iso_str = utc_now_isoformat(zulu=False, microseconds=False)
        assert iso_str.endswith('+00:00')
        assert '.' not in iso_str

        # Zulu with microseconds (default)
        iso_str = utc_now_isoformat(zulu=True, microseconds=True)
        assert iso_str.endswith('Z')
        assert '.' in iso_str

    def test_parseable_output(self):
        """Test that output can be parsed back to datetime."""
        iso_str = utc_now_isoformat()
        parsed_dt = parse_utc_datetime(iso_str)
        assert parsed_dt.tzinfo is timezone.utc


class TestParseUtcDatetime:
    """Tests for parse_utc_datetime function."""

    def test_parse_zulu_format(self):
        """Test parsing Z suffix format."""
        iso_str = "2023-01-01T12:00:00Z"
        dt = parse_utc_datetime(iso_str)
        
        assert dt.year == 2023
        assert dt.month == 1
        assert dt.day == 1
        assert dt.hour == 12
        assert dt.minute == 0
        assert dt.second == 0
        assert dt.tzinfo is timezone.utc

    def test_parse_offset_format(self):
        """Test parsing +00:00 offset format."""
        iso_str = "2023-01-01T12:00:00+00:00"
        dt = parse_utc_datetime(iso_str)
        
        assert dt.year == 2023
        assert dt.month == 1
        assert dt.day == 1
        assert dt.hour == 12
        assert dt.minute == 0
        assert dt.second == 0
        assert dt.tzinfo is timezone.utc

    def test_parse_with_microseconds(self):
        """Test parsing with microseconds."""
        iso_str = "2023-01-01T12:00:00.123456Z"
        dt = parse_utc_datetime(iso_str)
        
        assert dt.microsecond == 123456
        assert dt.tzinfo is timezone.utc

    def test_parse_invalid_format_raises_error(self):
        """Test that invalid format raises ValueError."""
        invalid_strings = [
            "not-a-date",
            "2023-01-01",  # Missing time
            "2023-01-01T12:00:00",  # Missing timezone
            "2023-01-01T12:00:00+05:00",  # Non-UTC timezone
        ]
        
        for invalid_str in invalid_strings:
            with pytest.raises(ValueError):
                parse_utc_datetime(invalid_str)

    def test_parse_non_utc_timezone_raises_error(self):
        """Test that non-UTC timezone raises ValueError."""
        iso_str = "2023-01-01T12:00:00+05:00"
        with pytest.raises(ValueError, match="Only UTC datetime strings are supported"):
            parse_utc_datetime(iso_str)

    def test_roundtrip_conversion(self):
        """Test that datetime can be converted to string and back."""
        original_dt = datetime(2023, 1, 1, 12, 0, 0, 123456, timezone.utc)
        iso_str = original_dt.isoformat().replace('+00:00', 'Z')
        parsed_dt = parse_utc_datetime(iso_str)
        
        assert original_dt == parsed_dt


class TestIsValidUtcIsoformat:
    """Tests for is_valid_utc_isoformat function."""

    def test_valid_zulu_format(self):
        """Test valid Z suffix format."""
        valid_strings = [
            "2023-01-01T12:00:00Z",
            "2023-01-01T12:00:00.123456Z",
            "2023-12-31T23:59:59Z",
        ]
        
        for valid_str in valid_strings:
            assert is_valid_utc_isoformat(valid_str) is True

    def test_valid_offset_format(self):
        """Test valid +00:00 offset format."""
        valid_strings = [
            "2023-01-01T12:00:00+00:00",
            "2023-01-01T12:00:00.123456+00:00",
        ]
        
        for valid_str in valid_strings:
            assert is_valid_utc_isoformat(valid_str) is True

    def test_invalid_formats(self):
        """Test invalid formats return False."""
        invalid_strings = [
            "not-a-date",
            "2023-01-01",
            "2023-01-01T12:00:00",  # Missing timezone
            "2023-01-01T12:00:00+05:00",  # Non-UTC timezone
            "",
            None,
            123,
        ]
        
        for invalid_str in invalid_strings:
            assert is_valid_utc_isoformat(invalid_str) is False

    def test_none_and_non_string_inputs(self):
        """Test that None and non-string inputs return False."""
        non_string_inputs = [None, 123, [], {}, datetime.now()]
        
        for input_val in non_string_inputs:
            assert is_valid_utc_isoformat(input_val) is False


class TestIntegration:
    """Integration tests combining multiple functions."""

    def test_complete_workflow(self):
        """Test complete workflow: generate -> format -> parse -> validate."""
        # Generate current UTC time
        dt = utc_now()
        
        # Format with Z suffix
        iso_str_z = utc_now_isoformat(zulu=True)
        assert is_valid_utc_isoformat(iso_str_z)
        parsed_z = parse_utc_datetime(iso_str_z)
        assert parsed_z.tzinfo is timezone.utc
        
        # Format with +00:00 suffix
        iso_str_offset = utc_now_isoformat(zulu=False)
        assert is_valid_utc_isoformat(iso_str_offset)
        parsed_offset = parse_utc_datetime(iso_str_offset)
        assert parsed_offset.tzinfo is timezone.utc

    def test_consistency_across_calls(self):
        """Test that multiple calls within short timeframe are consistent."""
        dt1 = utc_now()
        iso1 = utc_now_isoformat()
        dt2 = utc_now()
        iso2 = utc_now_isoformat()
        
        # Should be very close in time
        time_diff = (dt2 - dt1).total_seconds()
        assert time_diff < 1.0  # Less than 1 second apart
        
        # Should both be valid
        assert is_valid_utc_isoformat(iso1)
        assert is_valid_utc_isoformat(iso2)

    def test_edge_cases_and_error_handling(self):
        """Test edge cases and error handling."""
        # Empty string
        assert is_valid_utc_isoformat("") is False
        
        # Malformed strings
        malformed = ["2023-01-01T25:00:00Z", "2023-13-01T12:00:00Z"]
        for bad_str in malformed:
            assert is_valid_utc_isoformat(bad_str) is False
            with pytest.raises(ValueError):
                parse_utc_datetime(bad_str)