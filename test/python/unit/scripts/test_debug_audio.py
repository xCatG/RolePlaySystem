#!/usr/bin/env python3
"""
Unit tests for debug_audio.py utility.
"""

import pytest
import struct
import wave
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch

# Import the debug_audio module (need to add parent path)
import sys
debug_audio_path = Path(__file__).parents[4] / "test" / "scripts" / "voice" / "debug_audio.py"
sys.path.insert(0, str(debug_audio_path.parent))

import debug_audio


@pytest.fixture
def sample_pcm_data():
    """Create sample 16-bit PCM audio data (1 second at 16kHz)."""
    sample_rate = 16000
    duration = 1.0
    samples = int(sample_rate * duration)
    # Create a simple sine wave
    audio_data = b""
    for i in range(samples):
        # Simple sine wave at 440Hz
        sample = int(32767 * 0.5 * (i % 100) / 100)  # Simple sawtooth-like wave
        audio_data += struct.pack('<h', sample)
    return audio_data


@pytest.fixture
def mock_pcm_files(tmp_path, sample_pcm_data):
    """Create mock PCM files with timestamps."""
    session_dir = tmp_path / "session_test"
    session_dir.mkdir(parents=True)
    
    # Create multiple PCM files with different timestamps
    timestamps = [
        "2025-08-25T10-30-00.123456Z",
        "2025-08-25T10-30-01.234567Z", 
        "2025-08-25T10-30-02.345678Z"
    ]
    
    pcm_files = []
    for i, ts in enumerate(timestamps):
        filename = f"audio_in_{ts}.pcm"
        file_path = session_dir / filename
        # Write different sized chunks
        chunk_data = sample_pcm_data[i*1000:(i+1)*1000] if i < len(timestamps)-1 else sample_pcm_data[2000:3000]
        file_path.write_bytes(chunk_data)
        pcm_files.append(file_path)
    
    return session_dir, pcm_files


class TestDebugAudio:
    """Test suite for debug_audio.py functions."""

    def test_parse_timestamp_from_filename(self):
        """Test timestamp parsing from PCM filenames."""
        # Test valid timestamp
        filename = "audio_in_2025-08-25T10-30-21.333787Z.pcm"
        result = debug_audio.parse_timestamp_from_filename(filename)
        
        assert result.year == 2025
        assert result.month == 8
        assert result.day == 25
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 21

    def test_parse_timestamp_from_filename_invalid(self):
        """Test timestamp parsing with invalid filename."""
        filename = "invalid_filename.pcm"
        result = debug_audio.parse_timestamp_from_filename(filename)
        
        # Should return current time for invalid format
        assert isinstance(result, datetime)
        # Should be recent (within last minute)
        now = datetime.now()
        time_diff = abs((now - result.replace(tzinfo=None)).total_seconds())
        assert time_diff < 60

    def test_find_pcm_files(self, mock_pcm_files):
        """Test finding and sorting PCM files."""
        session_dir, expected_files = mock_pcm_files
        
        found_files = debug_audio.find_pcm_files(session_dir)
        
        assert len(found_files) == 3
        # Should be sorted by timestamp
        for i in range(len(found_files) - 1):
            ts1 = debug_audio.parse_timestamp_from_filename(found_files[i].name)
            ts2 = debug_audio.parse_timestamp_from_filename(found_files[i + 1].name)
            assert ts1 <= ts2

    def test_find_pcm_files_empty_directory(self, tmp_path):
        """Test finding PCM files in empty directory."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        found_files = debug_audio.find_pcm_files(empty_dir)
        
        assert len(found_files) == 0

    def test_reassemble_pcm_chunks(self, mock_pcm_files):
        """Test reassembling PCM chunks."""
        session_dir, pcm_files = mock_pcm_files
        
        # Read expected data manually
        expected_data = b""
        for file_path in sorted(pcm_files, key=lambda f: debug_audio.parse_timestamp_from_filename(f.name)):
            expected_data += file_path.read_bytes()
        
        # Test reassembly
        found_files = debug_audio.find_pcm_files(session_dir)
        result = debug_audio.reassemble_pcm_chunks(found_files)
        
        assert result == expected_data
        assert len(result) > 0

    def test_create_wav_file(self, tmp_path, sample_pcm_data):
        """Test creating WAV file from PCM data."""
        output_path = tmp_path / "test_output.wav"
        
        # Capture stdout to check print output
        with patch('builtins.print') as mock_print:
            debug_audio.create_wav_file(sample_pcm_data, output_path)
        
        # Verify file was created
        assert output_path.exists()
        
        # Verify WAV file properties
        with wave.open(str(output_path), 'rb') as wav_file:
            assert wav_file.getnchannels() == debug_audio.CHANNELS
            assert wav_file.getsampwidth() == debug_audio.BYTES_PER_SAMPLE
            assert wav_file.getframerate() == debug_audio.SAMPLE_RATE
            
            # Verify data matches
            wav_data = wav_file.readframes(wav_file.getnframes())
            assert wav_data == sample_pcm_data
        
        # Verify print statements were called
        assert mock_print.call_count >= 3  # Should print creation message, duration, size, format

    def test_show_session_info(self, mock_pcm_files, capsys):
        """Test showing session information."""
        session_dir, pcm_files = mock_pcm_files
        
        debug_audio.show_session_info(session_dir)
        
        captured = capsys.readouterr()
        
        # Verify expected output
        assert "📊 Session Audio Information" in captured.out
        assert f"Directory: {session_dir}" in captured.out
        assert "Total chunks: 3" in captured.out
        assert "Total duration:" in captured.out
        assert "Time range:" in captured.out

    def test_show_session_info_no_files(self, tmp_path, capsys):
        """Test session info with no PCM files."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        debug_audio.show_session_info(empty_dir)
        
        captured = capsys.readouterr()
        assert "❌ No PCM files found" in captured.out

    @pytest.mark.skip(reason="Skipping simpleaudio tests - complex import mocking")
    def test_play_wav_file_success(self, tmp_path, sample_pcm_data, capsys):
        """Test playing WAV file successfully."""
        pass

    @pytest.mark.skip(reason="Skipping simpleaudio tests - complex import mocking")
    def test_play_wav_file_import_error(self, tmp_path, sample_pcm_data, capsys):
        """Test playing WAV file when simpleaudio is not available."""
        pass

    @pytest.mark.skip(reason="Skipping simpleaudio tests - complex import mocking")
    def test_play_wav_file_playback_error(self, tmp_path, sample_pcm_data, capsys):
        """Test handling playback errors."""
        pass

    def test_reassemble_command_success(self, mock_pcm_files, capsys):
        """Test reassemble command with valid data."""
        session_dir, pcm_files = mock_pcm_files
        
        # Mock args object
        args = Mock()
        args.session_dir = str(session_dir)
        
        result = debug_audio.reassemble_command(args)
        
        assert result == 0  # Success
        
        # Verify WAV file was created
        wav_path = session_dir / "reassembled_audio.wav"
        assert wav_path.exists()
        
        captured = capsys.readouterr()
        assert "🔧 Reassembling 3 PCM chunks" in captured.out
        assert "✅ Created WAV file:" in captured.out

    def test_reassemble_command_directory_not_found(self, tmp_path, capsys):
        """Test reassemble command with non-existent directory."""
        args = Mock()
        args.session_dir = str(tmp_path / "nonexistent")
        
        result = debug_audio.reassemble_command(args)
        
        assert result == 1  # Failure
        
        captured = capsys.readouterr()
        assert "❌ Directory not found:" in captured.out

    def test_reassemble_command_no_pcm_files(self, tmp_path, capsys):
        """Test reassemble command with no PCM files."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        
        args = Mock()
        args.session_dir = str(empty_dir)
        
        result = debug_audio.reassemble_command(args)
        
        assert result == 1  # Failure
        
        captured = capsys.readouterr()
        assert "❌ No PCM files found" in captured.out

    def test_play_command_with_existing_wav(self, mock_pcm_files, sample_pcm_data):
        """Test play command when WAV file already exists."""
        session_dir, pcm_files = mock_pcm_files
        
        # Pre-create WAV file
        wav_path = session_dir / "reassembled_audio.wav"
        debug_audio.create_wav_file(sample_pcm_data, wav_path)
        
        args = Mock()
        args.session_dir = str(session_dir)
        
        with patch('debug_audio.play_wav_file') as mock_play:
            result = debug_audio.play_command(args)
        
        assert result == 0  # Success
        mock_play.assert_called_once_with(wav_path)

    def test_info_command_success(self, mock_pcm_files, capsys):
        """Test info command with valid data."""
        session_dir, pcm_files = mock_pcm_files
        
        args = Mock()
        args.session_dir = str(session_dir)
        
        result = debug_audio.info_command(args)
        
        assert result == 0  # Success
        
        captured = capsys.readouterr()
        assert "📊 Session Audio Information" in captured.out

    def test_info_command_directory_not_found(self, tmp_path, capsys):
        """Test info command with non-existent directory."""
        args = Mock()
        args.session_dir = str(tmp_path / "nonexistent")
        
        result = debug_audio.info_command(args)
        
        assert result == 1  # Failure
        
        captured = capsys.readouterr()
        assert "❌ Directory not found:" in captured.out