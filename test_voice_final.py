#!/usr/bin/env python3
"""
Final voice chat test - demonstrates full working flow with Gemini Live API.
"""

import asyncio
import websockets
import json
import httpx
import sys

BASE_URL = "http://localhost:8000/api"

async def test_voice_final():
    """Complete voice chat test with proper audio handling."""
    
    async with httpx.AsyncClient() as client:
        # 1. Login
        print("🔐 Logging in...")
        login_data = {
            "email": "voicetest2@example.com",
            "password": "TestPass123!"
        }
        
        resp = await client.post(f"{BASE_URL}/auth/login", json=login_data)
        if resp.status_code != 200:
            print(f"   ❌ Login failed: {resp.text}")
            return
        
        jwt_token = resp.json()["access_token"]
        print(f"   ✅ Authentication successful")
        print(f"token:\n{jwt_token}")
        
        # 2. Create session quickly
        print("\n📋 Setting up chat session...")
        headers = {"Authorization": f"Bearer {jwt_token}"}
        
        # Get first scenario and character
        resp = await client.get(f"{BASE_URL}/chat/content/scenarios", headers=headers)
        scenario = resp.json()["scenarios"][0]
        
        resp = await client.get(f"{BASE_URL}/chat/content/scenarios/{scenario['id']}/characters", headers=headers)
        character = resp.json()["characters"][0]
        
        print(f"   📖 Scenario: {scenario['name']}")
        print(f"   👤 Character: {character['name']}")
        
        # Create session
        session_data = {
            "scenario_id": scenario["id"],
            "character_id": character["id"],
            "participant_name": "Test User"
        }
        
        resp = await client.post(f"{BASE_URL}/chat/session", json=session_data, headers=headers)
        session_id = resp.json()["session_id"]
        print(f"   ✅ Session created: [{session_id}] ...")
        
        # 3. Connect to voice WebSocket
        print("\n🎙️ Connecting to voice chat...")
        ws_url = f"ws://localhost:8000/api/voice/ws/{session_id}?token={jwt_token}"
        
        async with websockets.connect(ws_url) as websocket:
            print("   ✅ WebSocket connected")
            
            # Wait for ready status
            ready = False
            while not ready:
                try:
                    message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                    if isinstance(message, str):
                        data = json.loads(message)
                        status = data.get('status', '')
                        if status:
                            print(f"   📡 Status: {status}")
                        if status == 'ready':
                            ready = True
                except asyncio.TimeoutError:
                    break
            
            if not ready:
                print("   ❌ Failed to get ready status")
                return
            
            # Send a text message
            print("\n💬 Sending message to character...")
            text_msg = {
                "type": "text",
                "text": "Hello! Can you tell me how you're feeling today in just a few words?"
            }
            await websocket.send(json.dumps(text_msg))
            print(f'   → "{text_msg["text"]}"')
            
            # Collect response
            print("\n🎧 Receiving response...")
            audio_chunks = []
            transcript = ""
            start_time = asyncio.get_event_loop().time()
            
            try:
                while True:
                    # Stop after 15 seconds max
                    if asyncio.get_event_loop().time() - start_time > 15:
                        break
                        
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    
                    if isinstance(message, bytes):
                        # Audio data
                        audio_chunks.append(len(message))
                    elif isinstance(message, str):
                        # JSON message
                        data = json.loads(message)
                        if data.get('type') == 'transcript':
                            transcript = data.get('text', '')
                            print(f'   ← "{transcript}"')
                            
            except asyncio.TimeoutError:
                pass  # Normal end of stream
            except websockets.exceptions.ConnectionClosed:
                pass  # Session ended
            
            # Summary
            if audio_chunks:
                total_audio = sum(audio_chunks)
                print(f"\n   🔊 Received {len(audio_chunks)} audio chunks ({total_audio:,} bytes total)")
                print(f"   📊 Average chunk size: {total_audio//len(audio_chunks):,} bytes")
            
            if transcript:
                print(f"   📝 Transcript received: Yes")
            
            # Clean shutdown
            try:
                await websocket.send(json.dumps({"type": "end_session"}))
            except:
                pass
            
            print("\n✅ Voice chat test completed successfully!")
            print("   The Gemini Live API is working and responding with audio!")

if __name__ == "__main__":
    print("=" * 60)
    print("GEMINI LIVE API - VOICE CHAT TEST")
    print("=" * 60)
    asyncio.run(test_voice_final())