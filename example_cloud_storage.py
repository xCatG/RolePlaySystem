#!/usr/bin/env python3
"""
Example script demonstrating cloud storage backends for chat logging.

This shows how to use the storage abstraction layer with different backends:
- FileStorage (local development with file locking)
- GCSStorage (Google Cloud Storage)
- S3Storage (AWS S3)

All backends implement the same interface, so ChatLogger works seamlessly
with any storage type based on configuration.
"""

import asyncio
import os
from pathlib import Path

# Add the source directory to Python path
import sys
sys.path.insert(0, str(Path(__file__).parent / "src" / "python"))

from role_play.common.storage import FileStorage, GCSStorage, S3Storage
from role_play.chat.chat_logger import ChatLogger


async def demo_file_storage():
    """Demo with local file storage (includes file locking)."""
    print("=== File Storage Demo ===")
    
    # Create a temporary directory for this demo
    demo_dir = Path("./demo_storage")
    demo_dir.mkdir(exist_ok=True)
    
    storage = FileStorage(str(demo_dir))
    chat_logger = ChatLogger(storage_backend=storage)
    
    # Start a session
    session_id = await chat_logger.start_session(
        user_id="demo_user",
        participant_name="Alice",
        scenario_id="scenario_1",
        scenario_name="Friendly Chat",
        character_id="char_1",
        character_name="Bob the Assistant",
        goal="Have a friendly conversation"
    )
    
    # Log some messages
    await chat_logger.log_message(session_id, "demo_user", "participant", "Hello!", 1)
    await chat_logger.log_message(session_id, "demo_user", "character", "Hi there! How are you?", 2)
    await chat_logger.log_message(session_id, "demo_user", "participant", "I'm doing great, thanks!", 3)
    
    # End the session
    await chat_logger.end_session(session_id, "demo_user", 3, 45.5, "Normal completion")
    
    # Export the session
    transcript = await chat_logger.export_session_text(session_id, "demo_user")
    print(f"Session {session_id} transcript:")
    print(transcript[:200] + "..." if len(transcript) > 200 else transcript)
    
    print(f"✅ File storage demo complete! Check {demo_dir}/logs/ for JSONL files")


async def demo_gcs_storage():
    """Demo with Google Cloud Storage (requires GCS_BUCKET_NAME environment variable)."""
    print("\n=== Google Cloud Storage Demo ===")
    
    bucket_name = os.getenv("GCS_BUCKET_NAME")
    if not bucket_name:
        print("⚠️  Skipping GCS demo - GCS_BUCKET_NAME environment variable not set")
        return
    
    try:
        storage = GCSStorage(
            bucket_name=bucket_name,
            project_id=os.getenv("GCS_PROJECT_ID"),
            credentials_path=os.getenv("GCS_CREDENTIALS_PATH"),
            prefix="demo/"
        )
        chat_logger = ChatLogger(storage_backend=storage)
        
        session_id = await chat_logger.start_session(
            user_id="gcs_user",
            participant_name="Charlie",
            scenario_id="scenario_2",
            scenario_name="Cloud Chat",
            character_id="char_2",
            character_name="GCS Assistant"
        )
        
        await chat_logger.log_message(session_id, "gcs_user", "participant", "Testing GCS!", 1)
        await chat_logger.log_message(session_id, "gcs_user", "character", "GCS storage is working!", 2)
        
        await chat_logger.end_session(session_id, "gcs_user", 2, 30.0, "GCS test complete")
        
        print(f"✅ GCS demo complete! Session {session_id} stored in gs://{bucket_name}/demo/logs/")
        
    except Exception as e:
        print(f"❌ GCS demo failed: {e}")


async def demo_s3_storage():
    """Demo with AWS S3 (requires S3_BUCKET_NAME environment variable)."""
    print("\n=== AWS S3 Storage Demo ===")
    
    bucket_name = os.getenv("S3_BUCKET_NAME")
    if not bucket_name:
        print("⚠️  Skipping S3 demo - S3_BUCKET_NAME environment variable not set")
        return
    
    try:
        storage = S3Storage(
            bucket_name=bucket_name,
            region_name=os.getenv("S3_REGION_NAME", "us-east-1"),
            aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
            prefix="demo/"
        )
        chat_logger = ChatLogger(storage_backend=storage)
        
        session_id = await chat_logger.start_session(
            user_id="s3_user",
            participant_name="Dave",
            scenario_id="scenario_3",
            scenario_name="S3 Chat",
            character_id="char_3",
            character_name="S3 Assistant"
        )
        
        await chat_logger.log_message(session_id, "s3_user", "participant", "Testing S3!", 1)
        await chat_logger.log_message(session_id, "s3_user", "character", "S3 storage is working!", 2)
        
        await chat_logger.end_session(session_id, "s3_user", 2, 25.0, "S3 test complete")
        
        print(f"✅ S3 demo complete! Session {session_id} stored in s3://{bucket_name}/demo/logs/")
        
    except Exception as e:
        print(f"❌ S3 demo failed: {e}")


async def main():
    """Run all storage demos."""
    print("🚀 Cloud Storage Backend Demo")
    print("=" * 50)
    
    await demo_file_storage()
    await demo_gcs_storage()
    await demo_s3_storage()
    
    print("\n" + "=" * 50)
    print("Demo complete! 🎉")
    print("\nTo test cloud storage backends, set these environment variables:")
    print("• For GCS: GCS_BUCKET_NAME, GCS_PROJECT_ID (optional), GCS_CREDENTIALS_PATH (optional)")
    print("• For S3: S3_BUCKET_NAME, S3_REGION_NAME (optional), S3_ACCESS_KEY_ID (optional), S3_SECRET_ACCESS_KEY (optional)")


if __name__ == "__main__":
    asyncio.run(main())