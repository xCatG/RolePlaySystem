#!/usr/bin/env python3
"""
Voice Backend Automated Test Script

This script performs comprehensive testing of the voice backend:
1. Authentication and session creation
2. WebSocket connection establishment
3. Text message sending and response verification
4. Audio message simulation
5. Transcript capture verification
6. Error handling and cleanup

Usage:
    python test/voice/test_voice_backend.py [--user email] [--password pass] [--verbose]
"""

import asyncio
import websockets
import json
import httpx
import sys
import base64
import argparse
import time
from typing import Optional, Dict, Any, List
from pathlib import Path

BASE_URL = "http://localhost:8000/api"

class VoiceBackendTester:
    """Comprehensive voice backend testing class."""
    
    def __init__(self, email: str = "test@example.com", password: str = "password", verbose: bool = False):
        self.email = email
        self.password = password
        self.verbose = verbose
        self.jwt_token: Optional[str] = None
        self.session_id: Optional[str] = None
        self.ws_url: Optional[str] = None
        self.test_results: List[Dict[str, Any]] = []
        
    def log(self, message: str, level: str = "INFO"):
        """Log message with optional verbosity control."""
        if level == "ERROR" or self.verbose:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] {level}: {message}")
    
    def add_test_result(self, test_name: str, success: bool, details: str = "", duration: float = 0):
        """Record test result."""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "duration": duration
        }
        self.test_results.append(result)
        
        status = "✅" if success else "❌"
        duration_str = f" ({duration:.2f}s)" if duration > 0 else ""
        print(f"  {status} {test_name}{duration_str}")
        if details and (not success or self.verbose):
            print(f"     {details}")
    
    async def setup_session(self) -> bool:
        """Setup authentication and create chat session."""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient() as client:
                # 1. Login
                self.log("Authenticating with backend...")
                login_data = {"email": self.email, "password": self.password}
                resp = await client.post(f"{BASE_URL}/auth/login", json=login_data, timeout=10.0)
                
                if resp.status_code != 200:
                    self.add_test_result(
                        "Authentication", 
                        False, 
                        f"Login failed: {resp.status_code} {resp.text[:100]}"
                    )
                    return False
                
                self.jwt_token = resp.json()["access_token"]
                self.add_test_result("Authentication", True, f"Logged in as {self.email}")
                
                # 2. Get content for session creation
                headers = {"Authorization": f"Bearer {self.jwt_token}"}
                
                # Get scenarios
                resp = await client.get(f"{BASE_URL}/chat/content/scenarios", headers=headers)
                if resp.status_code != 200:
                    self.add_test_result("Content Loading", False, "Failed to get scenarios")
                    return False
                    
                scenarios = resp.json()["scenarios"]
                if not scenarios:
                    self.add_test_result("Content Loading", False, "No scenarios available")
                    return False
                    
                scenario = scenarios[0]
                
                # Get characters
                resp = await client.get(
                    f"{BASE_URL}/chat/content/scenarios/{scenario['id']}/characters", 
                    headers=headers
                )
                characters = resp.json()["characters"]
                if not characters:
                    self.add_test_result("Content Loading", False, "No characters available")
                    return False
                    
                character = characters[0]
                self.add_test_result(
                    "Content Loading", 
                    True, 
                    f"Using {scenario['name']} with {character['name']}"
                )
                
                # 3. Create session
                session_data = {
                    "scenario_id": scenario["id"],
                    "character_id": character["id"],
                    "participant_name": "Voice Test Bot"
                }
                
                resp = await client.post(f"{BASE_URL}/chat/session", json=session_data, headers=headers)
                if resp.status_code != 200:
                    self.add_test_result("Session Creation", False, f"Failed: {resp.text[:100]}")
                    return False
                    
                self.session_id = resp.json()["session_id"]
                self.ws_url = f"ws://localhost:8000/api/voice/ws/{self.session_id}?token={self.jwt_token}"
                
                duration = time.time() - start_time
                self.add_test_result(
                    "Session Creation", 
                    True, 
                    f"Created session {self.session_id}", 
                    duration
                )
                
                return True
                
        except Exception as e:
            duration = time.time() - start_time
            self.add_test_result("Setup", False, f"Exception: {str(e)}", duration)
            return False
    
    async def test_websocket_connection(self) -> bool:
        """Test WebSocket connection establishment."""
        start_time = time.time()
        
        try:
            async with websockets.connect(self.ws_url, open_timeout=10) as websocket:
                self.log("WebSocket connected, waiting for ready status...")
                
                # Wait for ready status
                ready = False
                config_received = False
                timeout_count = 0
                max_timeouts = 10
                
                while not ready and timeout_count < max_timeouts:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)
                        
                        self.log(f"Received: {data.get('type', 'unknown')} - {data}", "DEBUG")
                        
                        if data.get('type') == 'error':
                            self.log(f"WebSocket error: {data.get('error', 'Unknown error')}", "ERROR")
                            break
                        elif data.get('type') == 'config':
                            config_received = True
                            self.log(f"Config: {data.get('audio_format')} @ {data.get('sample_rate')}Hz")
                            
                        elif data.get('type') == 'status':
                            status = data.get('status', '')
                            if status == 'ready':
                                ready = True
                                break
                                
                    except asyncio.TimeoutError:
                        timeout_count += 1
                        continue
                
                duration = time.time() - start_time
                
                if ready and config_received:
                    self.add_test_result(
                        "WebSocket Connection", 
                        True, 
                        "Connected and received ready status", 
                        duration
                    )
                    return True
                else:
                    self.add_test_result(
                        "WebSocket Connection", 
                        False, 
                        f"Timeout waiting for ready (config: {config_received})", 
                        duration
                    )
                    return False
                    
        except Exception as e:
            duration = time.time() - start_time
            self.add_test_result("WebSocket Connection", False, str(e), duration)
            return False
    
    async def test_text_messaging(self) -> bool:
        """Test text message sending and response."""
        start_time = time.time()
        
        try:
            async with websockets.connect(self.ws_url) as websocket:
                # Wait for ready
                await self._wait_for_ready(websocket)
                
                # Send text message
                test_message = "Hello! Please respond with just 'Hi there!' to confirm you received this."
                text_base64 = base64.b64encode(test_message.encode('utf-8')).decode('ascii')
                
                message = {
                    "mime_type": "text/plain",
                    "data": text_base64,
                    "end_session": False
                }
                
                await websocket.send(json.dumps(message))
                self.log(f"Sent text: '{test_message}'")
                
                # Wait for response
                transcript_received = False
                audio_received = False
                response_text = ""
                
                start_wait = time.time()
                while time.time() - start_wait < 15:  # 15 second timeout
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                        data = json.loads(response)
                        
                        if data.get('type') == 'transcript_final':
                            transcript_received = True
                            response_text = data.get('text', '')
                            self.log(f"Received transcript: '{response_text}'")
                            
                        elif data.get('type') == 'audio':
                            audio_received = True
                            self.log(f"Received audio chunk: {len(data.get('data', ''))} chars")
                            
                        elif data.get('type') == 'turn_status' and data.get('turn_complete'):
                            self.log("Turn completed")
                            break
                            
                    except asyncio.TimeoutError:
                        continue
                
                duration = time.time() - start_time
                
                # Evaluate results
                if transcript_received and audio_received:
                    self.add_test_result(
                        "Text Messaging", 
                        True, 
                        f"Received transcript and audio. Response: '{response_text[:50]}...'", 
                        duration
                    )
                    return True
                else:
                    missing = []
                    if not transcript_received:
                        missing.append("transcript")
                    if not audio_received:
                        missing.append("audio")
                    
                    self.add_test_result(
                        "Text Messaging", 
                        False, 
                        f"Missing: {', '.join(missing)}", 
                        duration
                    )
                    return False
                    
        except Exception as e:
            duration = time.time() - start_time
            self.add_test_result("Text Messaging", False, str(e), duration)
            return False
    
    async def test_audio_simulation(self) -> bool:
        """Test simulated audio message sending."""
        start_time = time.time()
        
        try:
            async with websockets.connect(self.ws_url) as websocket:
                await self._wait_for_ready(websocket)
                
                # Generate fake audio data (1 second of silent PCM)
                sample_rate = 16000
                duration_seconds = 1
                samples = sample_rate * duration_seconds
                
                # Create silent audio (16-bit PCM)
                import struct
                audio_data = b''.join(struct.pack('<h', 0) for _ in range(samples))
                audio_base64 = base64.b64encode(audio_data).decode('ascii')
                
                message = {
                    "mime_type": "audio/pcm",
                    "data": audio_base64,
                    "end_session": False
                }
                
                await websocket.send(json.dumps(message))
                self.log(f"Sent audio data: {len(audio_data)} bytes")
                
                # Wait for any response
                response_received = False
                start_wait = time.time()
                
                while time.time() - start_wait < 10:  # 10 second timeout
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(response)
                        response_received = True
                        self.log(f"Received response type: {data.get('type')}")
                        
                        if data.get('type') == 'turn_status' and data.get('turn_complete'):
                            break
                            
                    except asyncio.TimeoutError:
                        continue
                
                duration = time.time() - start_time
                
                if response_received:
                    self.add_test_result(
                        "Audio Simulation", 
                        True, 
                        "Audio message processed successfully", 
                        duration
                    )
                    return True
                else:
                    self.add_test_result(
                        "Audio Simulation", 
                        False, 
                        "No response to audio message", 
                        duration
                    )
                    return False
                    
        except Exception as e:
            duration = time.time() - start_time
            self.add_test_result("Audio Simulation", False, str(e), duration)
            return False
    
    async def test_graceful_disconnect(self) -> bool:
        """Test graceful session termination."""
        start_time = time.time()
        
        try:
            async with websockets.connect(self.ws_url) as websocket:
                await self._wait_for_ready(websocket)
                
                # Send end session message
                end_message = {
                    "mime_type": "text/plain",
                    "data": "",
                    "end_session": True
                }
                
                await websocket.send(json.dumps(end_message))
                self.log("Sent end session message")
                
                # Wait for connection to close gracefully
                closed_gracefully = False
                try:
                    await asyncio.wait_for(websocket.recv(), timeout=3.0)
                except websockets.exceptions.ConnectionClosed:
                    closed_gracefully = True
                except asyncio.TimeoutError:
                    pass
                
                duration = time.time() - start_time
                
                if closed_gracefully:
                    self.add_test_result(
                        "Graceful Disconnect", 
                        True, 
                        "Session ended cleanly", 
                        duration
                    )
                    return True
                else:
                    self.add_test_result(
                        "Graceful Disconnect", 
                        False, 
                        "Connection did not close gracefully", 
                        duration
                    )
                    return False
                    
        except Exception as e:
            duration = time.time() - start_time
            self.add_test_result("Graceful Disconnect", False, str(e), duration)
            return False
    
    async def test_error_handling(self) -> bool:
        """Test error handling with invalid data."""
        start_time = time.time()
        
        try:
            async with websockets.connect(self.ws_url) as websocket:
                await self._wait_for_ready(websocket)
                
                # Send invalid message
                invalid_message = {
                    "mime_type": "invalid/type",
                    "data": "invalid_base64_data!!!",
                    "end_session": False
                }
                
                await websocket.send(json.dumps(invalid_message))
                self.log("Sent invalid message")
                
                # Check if we get an error response or connection stays stable
                error_handled = False
                connection_stable = True
                
                try:
                    for _ in range(5):  # Check for 5 seconds
                        response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(response)
                        
                        if data.get('type') == 'error':
                            error_handled = True
                            self.log(f"Received error response: {data.get('error', '')}")
                            break
                            
                except asyncio.TimeoutError:
                    pass  # No response is also valid
                except websockets.exceptions.ConnectionClosed:
                    connection_stable = False
                
                duration = time.time() - start_time
                
                if connection_stable:
                    self.add_test_result(
                        "Error Handling", 
                        True, 
                        f"Connection stable, error handled: {error_handled}", 
                        duration
                    )
                    return True
                else:
                    self.add_test_result(
                        "Error Handling", 
                        False, 
                        "Connection closed unexpectedly", 
                        duration
                    )
                    return False
                    
        except Exception as e:
            duration = time.time() - start_time
            self.add_test_result("Error Handling", False, str(e), duration)
            return False
    
    async def _wait_for_ready(self, websocket, timeout: float = 10.0) -> bool:
        """Wait for WebSocket to reach ready state."""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                data = json.loads(message)
                
                if data.get('type') == 'status' and data.get('status') == 'ready':
                    return True
                    
            except asyncio.TimeoutError:
                continue
        
        return False
    
    async def run_all_tests(self) -> bool:
        """Run complete test suite."""
        print("🎙️  Voice Backend Automated Test Suite")
        print("=" * 60)
        
        overall_start = time.time()
        
        # 1. Setup
        if not await self.setup_session():
            return False
        
        # 2. Core tests
        tests = [
            self.test_websocket_connection,
            self.test_text_messaging,
            self.test_audio_simulation,
            self.test_graceful_disconnect,
            self.test_error_handling,
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            if await test():
                passed += 1
        
        # 3. Results summary
        overall_duration = time.time() - overall_start
        success_rate = (passed / total) * 100 if total > 0 else 0
        
        print("\n" + "=" * 60)
        print("📊 Test Results Summary")
        print("=" * 60)
        
        for result in self.test_results:
            status = "✅" if result["success"] else "❌"
            duration = f" ({result['duration']:.2f}s)" if result["duration"] > 0 else ""
            print(f"{status} {result['test']}{duration}")
            if result["details"] and (not result["success"] or self.verbose):
                print(f"   └─ {result['details']}")
        
        print(f"\n📈 Overall: {passed}/{total} tests passed ({success_rate:.1f}%)")
        print(f"⏱️  Total time: {overall_duration:.2f}s")
        
        if passed == total:
            print("🎉 All tests passed! Voice backend is working correctly.")
            return True
        else:
            print(f"⚠️  {total - passed} test(s) failed. Check the details above.")
            return False

async def main():
    parser = argparse.ArgumentParser(description='Test voice backend functionality')
    parser.add_argument('--user', default='test@example.com', help='Login email')
    parser.add_argument('--password', default='password', help='Login password')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()
    
    tester = VoiceBackendTester(args.user, args.password, args.verbose)
    
    try:
        success = await tester.run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test suite failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())