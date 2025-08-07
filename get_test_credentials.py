#!/usr/bin/env python3
"""
Quick script to get test credentials for the HTML voice chat test.
"""

import asyncio
import httpx
import json

BASE_URL = "http://localhost:8000/api"

async def get_credentials():
    async with httpx.AsyncClient() as client:
        # Login
        print("Logging in...")
        login_data = {
            "email": "voicetest2@example.com",
            "password": "TestPass123!"
        }
        
        resp = await client.post(f"{BASE_URL}/auth/login", json=login_data)
        if resp.status_code != 200:
            print(f"Login failed: {resp.text}")
            return
        
        jwt_token = resp.json()["access_token"]
        print("\n✅ JWT Token (copy this):")
        print(jwt_token)
        
        # Create session
        headers = {"Authorization": f"Bearer {jwt_token}"}
        
        # Get first scenario and character
        resp = await client.get(f"{BASE_URL}/chat/content/scenarios", headers=headers)
        scenario = resp.json()["scenarios"][0]
        
        resp = await client.get(f"{BASE_URL}/chat/content/scenarios/{scenario['id']}/characters", headers=headers)
        character = resp.json()["characters"][0]
        
        # Create session
        session_data = {
            "scenario_id": scenario["id"],
            "character_id": character["id"],
            "participant_name": "Test User"
        }
        
        resp = await client.post(f"{BASE_URL}/chat/session", json=session_data, headers=headers)
        session_id = resp.json()["session_id"]
        
        print(f"\n✅ Session ID (copy this):")
        print(session_id)
        
        print(f"\n📝 Session Details:")
        print(f"   Scenario: {scenario['name']}")
        print(f"   Character: {character['name']}")
        
        print("\n🌐 Now open test_voice_chat.html in your browser and paste these values!")

if __name__ == "__main__":
    asyncio.run(get_credentials())