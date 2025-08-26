#!/usr/bin/env python3
"""
Debug Audio Utility for Voice Chat PCM Files

This script helps debug voice chat by:
1. Reassembling PCM chunks into playable audio
2. Converting PCM to WAV format
3. Playing back audio for debugging

Usage:
    python debug_audio.py reassemble <session_dir>  # Combine PCM chunks
    python debug_audio.py play <session_dir>        # Play reassembled audio
    python debug_audio.py info <session_dir>        # Show audio info
"""

import asyncio
import wave
import struct
import sys
from pathlib import Path
from typing import List, Tuple
import argparse
from datetime import datetime

# Audio configuration matching VoiceConfig
SAMPLE_RATE = 16000  # 16kHz input
CHANNELS = 1         # Mono
BIT_DEPTH = 16      # 16-bit
BYTES_PER_SAMPLE = BIT_DEPTH // 8


def parse_timestamp_from_filename(filename: str) -> datetime:
    """Extract timestamp from PCM filename."""
    # Format: audio_in_2025-08-25T23-45-21.333787Z.pcm
    timestamp_str = filename.replace("audio_in_", "").replace(".pcm", "")
    # Convert back to ISO format (replace - with : in time part)
    parts = timestamp_str.split("T")
    if len(parts) == 2:
        date_part = parts[0]
        time_part = parts[1].replace("Z", "").replace("-", ":")
        iso_str = f"{date_part}T{time_part}Z"
        return datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    return datetime.now()


def find_pcm_files(session_dir: Path) -> List[Path]:
    """Find all PCM files in session directory, sorted by timestamp."""
    pcm_files = list(session_dir.glob("audio_in_*.pcm"))
    
    # Sort by timestamp in filename
    pcm_files.sort(key=lambda f: parse_timestamp_from_filename(f.name))
    
    return pcm_files


def reassemble_pcm_chunks(pcm_files: List[Path]) -> bytes:
    """Reassemble PCM chunks into single audio stream."""
    audio_data = b""
    
    for pcm_file in pcm_files:
        chunk_data = pcm_file.read_bytes()
        audio_data += chunk_data
        
    return audio_data


def create_wav_file(pcm_data: bytes, output_path: Path, sample_rate: int = SAMPLE_RATE):
    """Create WAV file from raw PCM data."""
    with wave.open(str(output_path), 'wb') as wav_file:
        wav_file.setnchannels(CHANNELS)
        wav_file.setsampwidth(BYTES_PER_SAMPLE)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    
    print(f"✅ Created WAV file: {output_path}")
    
    # Calculate duration
    num_samples = len(pcm_data) // BYTES_PER_SAMPLE
    duration_seconds = num_samples / sample_rate
    print(f"   Duration: {duration_seconds:.2f} seconds")
    print(f"   Size: {len(pcm_data):,} bytes")
    print(f"   Format: {sample_rate}Hz, {BIT_DEPTH}-bit, {'mono' if CHANNELS == 1 else 'stereo'}")


def play_wav_file(wav_path: Path):
    """Play WAV file using system audio (requires pyaudio or simpleaudio)."""
    try:
        # Try using simpleaudio first (simpler API)
        import simpleaudio as sa
        wave_obj = sa.WaveObject.from_wave_file(str(wav_path))
        play_obj = wave_obj.play()
        print(f"🔊 Playing audio: {wav_path}")
        play_obj.wait_done()
        print("✅ Playback complete")
    except ImportError:
        print("⚠️  simpleaudio not installed. Install with: pip install simpleaudio")
        print(f"   You can play the file manually: {wav_path}")
    except Exception as e:
        print(f"❌ Error playing audio: {e}")
        print(f"   You can play the file manually: {wav_path}")


def show_session_info(session_dir: Path):
    """Display information about PCM files in session."""
    pcm_files = find_pcm_files(session_dir)
    
    if not pcm_files:
        print(f"❌ No PCM files found in {session_dir}")
        return
    
    print(f"📊 Session Audio Information")
    print(f"   Directory: {session_dir}")
    print(f"   Total chunks: {len(pcm_files)}")
    
    # Calculate total duration
    total_bytes = sum(f.stat().st_size for f in pcm_files)
    total_samples = total_bytes // BYTES_PER_SAMPLE
    total_duration = total_samples / SAMPLE_RATE
    
    print(f"   Total size: {total_bytes:,} bytes")
    print(f"   Total duration: {total_duration:.2f} seconds")
    
    # Show time range
    first_time = parse_timestamp_from_filename(pcm_files[0].name)
    last_time = parse_timestamp_from_filename(pcm_files[-1].name)
    time_span = (last_time - first_time).total_seconds()
    
    print(f"   Time range: {time_span:.2f} seconds")
    print(f"   First chunk: {first_time.isoformat()}")
    print(f"   Last chunk: {last_time.isoformat()}")
    
    # Check chunk sizes
    chunk_sizes = {f.stat().st_size for f in pcm_files}
    if len(chunk_sizes) == 1:
        print(f"   Chunk size: {list(chunk_sizes)[0]} bytes (uniform)")
    else:
        print(f"   Chunk sizes: {min(chunk_sizes)}-{max(chunk_sizes)} bytes (variable)")


def reassemble_command(args):
    """Handle reassemble command."""
    session_dir = Path(args.session_dir)
    if not session_dir.exists():
        print(f"❌ Directory not found: {session_dir}")
        return 1
    
    pcm_files = find_pcm_files(session_dir)
    if not pcm_files:
        print(f"❌ No PCM files found in {session_dir}")
        return 1
    
    print(f"🔧 Reassembling {len(pcm_files)} PCM chunks...")
    pcm_data = reassemble_pcm_chunks(pcm_files)
    
    # Create output filename
    output_path = session_dir / "reassembled_audio.wav"
    create_wav_file(pcm_data, output_path)
    
    return 0


def play_command(args):
    """Handle play command."""
    session_dir = Path(args.session_dir)
    if not session_dir.exists():
        print(f"❌ Directory not found: {session_dir}")
        return 1
    
    # Check if already reassembled
    wav_path = session_dir / "reassembled_audio.wav"
    if not wav_path.exists():
        print("🔧 Reassembling audio first...")
        pcm_files = find_pcm_files(session_dir)
        if not pcm_files:
            print(f"❌ No PCM files found in {session_dir}")
            return 1
        
        pcm_data = reassemble_pcm_chunks(pcm_files)
        create_wav_file(pcm_data, wav_path)
    
    play_wav_file(wav_path)
    return 0


def info_command(args):
    """Handle info command."""
    session_dir = Path(args.session_dir)
    if not session_dir.exists():
        print(f"❌ Directory not found: {session_dir}")
        return 1
    
    show_session_info(session_dir)
    return 0


def main():
    parser = argparse.ArgumentParser(description='Debug audio utility for voice chat PCM files')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Reassemble command
    reassemble_parser = subparsers.add_parser('reassemble', help='Reassemble PCM chunks into WAV')
    reassemble_parser.add_argument('session_dir', help='Path to session directory with PCM files')
    reassemble_parser.set_defaults(func=reassemble_command)
    
    # Play command
    play_parser = subparsers.add_parser('play', help='Play reassembled audio')
    play_parser.add_argument('session_dir', help='Path to session directory')
    play_parser.set_defaults(func=play_command)
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show session audio information')
    info_parser.add_argument('session_dir', help='Path to session directory')
    info_parser.set_defaults(func=info_command)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())