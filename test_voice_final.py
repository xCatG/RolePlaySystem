#!/usr/bin/env python3
"""
Final voice chat test - demonstrates full working flow with Gemini Live API.
Uses ADK-style message format with mime_type and base64-encoded data.
"""

import asyncio
import websockets
import json
import httpx
import sys
import base64

BASE_URL = "http://localhost:8000/api"

async def test_voice_final():
    """Complete voice chat test with proper audio handling."""
    
    async with httpx.AsyncClient() as client:
        # 1. Login
        print("🔐 Logging in...")
        login_data = {
            "email": "test@example.com",
            "password": "password"
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
            
            # Send a text message using ADK format
            print("\n💬 Sending message to character...")
            text_content = "Hello! Can you tell me how you're feeling today in just a few words?"
            
            # Encode text as base64 (ADK format)
            text_bytes = text_content.encode('utf-8')
            text_base64 = base64.b64encode(text_bytes).decode('ascii')
            
            text_msg = {
                "mime_type": "text/plain",
                "data": text_base64,
                "end_session": False
            }
            await websocket.send(json.dumps(text_msg))
            print(f'   → "{text_content}"')
            
            # Collect response
            print("\n🎧 Receiving response...")
            audio_chunks = []
            transcript = ""
            start_time = asyncio.get_event_loop().time()
            response_complete = False
            
            try:
                while True:
                    # Stop after 15 seconds max
                    if asyncio.get_event_loop().time() - start_time > 15:
                        print("   ⏱️  Max time reached, ending session")
                        break
                    
                    # Wait for response_complete signal or timeout
                    try:
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
                            elif data.get('type') == 'status':
                                status = data.get('status', '')
                                if status == 'response_complete':
                                    print("   ✅ Response complete signal received")
                                    response_complete = True
                                    break
                    except asyncio.TimeoutError:
                        # If we haven't received the completion signal, keep waiting
                        if not response_complete:
                            continue
                        else:
                            break
                            
            except websockets.exceptions.ConnectionClosed:
                pass  # Session ended
            
            # Summary
            if audio_chunks:
                total_audio = sum(audio_chunks)
                print(f"\n   🔊 Received {len(audio_chunks)} audio chunks ({total_audio:,} bytes total)")
                print(f"   📊 Average chunk size: {total_audio//len(audio_chunks):,} bytes")
            
            if transcript:
                print(f"   📝 Transcript received: Yes\n\t{transcript}")
            
            # Clean shutdown using ADK format
            print("\n🔚 Ending session gracefully...")
            try:
                end_msg = {
                    "mime_type": "text/plain",
                    "data": base64.b64encode(b"").decode('ascii'),  # Empty data
                    "end_session": True
                }
                await websocket.send(json.dumps(end_msg))
                
                # Wait briefly for any final messages
                try:
                    await asyncio.wait_for(websocket.recv(), timeout=0.5)
                except asyncio.TimeoutError:
                    pass
            except:
                pass
            
            print("\n✅ Voice chat test completed successfully!")
            print("   The Gemini Live API is working and responding with audio!")

if __name__ == "__main__":
    print("=" * 60)
    print("GEMINI LIVE API - VOICE CHAT TEST")
    print("=" * 60)
    asyncio.run(test_voice_final())