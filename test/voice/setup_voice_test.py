#!/usr/bin/env python3
"""
Voice Test Setup Script

This script creates a voice testing session by:
1. Logging in with test credentials
2. Creating a chat session with scenario/character
3. Generating an HTML test page with embedded credentials
4. Providing instructions for testing

Usage:
    python test/voice/setup_voice_test.py [--user email] [--password pass]
"""

import asyncio
import httpx
import sys
import os
import argparse
from pathlib import Path
from urllib.parse import quote

BASE_URL = "http://localhost:8000/api"
HTML_TEMPLATE_FILE = "voice_test_template.html"
OUTPUT_HTML_FILE = "test_session.html"

async def create_voice_test_session(email="test@example.com", password="password"):
    """Create a complete voice test session setup."""
    
    print("🎙️  Voice Backend Test Setup")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        # 1. Login and get JWT token
        print("🔐 Authenticating...")
        try:
            login_data = {"email": email, "password": password}
            resp = await client.post(f"{BASE_URL}/auth/login", json=login_data)
            
            if resp.status_code != 200:
                print(f"   ❌ Login failed: {resp.text}")
                print(f"   💡 Try: python run_server.py first, then create test user")
                return False
            
            jwt_token = resp.json()["access_token"]
            print(f"   ✅ Authenticated as {email}")
            
        except Exception as e:
            print(f"   ❌ Connection failed: {e}")
            print(f"   💡 Make sure server is running: python src/python/run_server.py")
            return False

        # 2. Get available content
        print("\n📋 Setting up chat session...")
        headers = {"Authorization": f"Bearer {jwt_token}"}
        
        try:
            # Get scenarios
            resp = await client.get(f"{BASE_URL}/chat/content/scenarios", headers=headers)
            scenarios = resp.json()["scenarios"]
            
            if not scenarios:
                print("   ❌ No scenarios available")
                return False
                
            scenario = scenarios[0]
            print(f"   📖 Using scenario: {scenario['name']}")
            
            # Get characters for this scenario
            resp = await client.get(f"{BASE_URL}/chat/content/scenarios/{scenario['id']}/characters", headers=headers)
            characters = resp.json()["characters"]
            
            if not characters:
                print("   ❌ No characters available for scenario")
                return False
                
            character = characters[0]
            print(f"   👤 Using character: {character['name']}")
            
        except Exception as e:
            print(f"   ❌ Failed to get content: {e}")
            return False

        # 3. Create chat session
        try:
            session_data = {
                "scenario_id": scenario["id"],
                "character_id": character["id"],
                "participant_name": "Voice Test User"
            }
            
            resp = await client.post(f"{BASE_URL}/chat/session", json=session_data, headers=headers)
            if resp.status_code != 200:
                print(f"   ❌ Session creation failed: {resp.text}")
                return False
                
            session_id = resp.json()["session_id"]
            print(f"   ✅ Session created: {session_id}")
            
        except Exception as e:
            print(f"   ❌ Failed to create session: {e}")
            return False

        # 4. Generate HTML test page
        print("\n🌐 Generating test page...")
        try:
            test_dir = Path(__file__).parent
            html_content = generate_test_html(jwt_token, session_id, scenario, character)
            
            output_path = test_dir / OUTPUT_HTML_FILE
            with open(output_path, 'w') as f:
                f.write(html_content)
                
            print(f"   ✅ Test page created: {output_path}")
            
        except Exception as e:
            print(f"   ❌ Failed to create HTML: {e}")
            return False

        # 5. Print instructions
        print("\n🚀 Ready to test!")
        print("=" * 50)
        print("📁 Files created:")
        print(f"   • {output_path}")
        print("\n🌐 Open in browser:")
        print(f"   • file://{output_path.absolute()}")
        print("\n🖥️  Or start local server:")
        print(f"   • cd {test_dir}")
        print(f"   • python -m http.server 8080")
        print(f"   • Open: http://localhost:8080/{OUTPUT_HTML_FILE}")
        print("\n🎯 Test with:")
        print("   • JWT Token and Session ID are pre-filled")
        print("   • Click 'Connect' to start voice session")
        print("   • Use 'Push to Talk' or type text messages")
        print("   • Check browser dev tools for WebSocket messages")
        print("\n💡 Credentials:")
        print(f"   • JWT: {jwt_token[:50]}...")
        print(f"   • Session: {session_id}")
        
        return True

def generate_test_html(jwt_token, session_id, scenario, character):
    """Generate HTML test page with embedded credentials."""
    
    # Read the template from the same directory or create inline
    test_dir = Path(__file__).parent
    template_path = test_dir / HTML_TEMPLATE_FILE
    
    if template_path.exists():
        with open(template_path, 'r') as f:
            template = f.read()
    else:
        # Use inline template if file doesn't exist
        template = create_inline_html_template()
    
    # Replace placeholders
    html_content = template.replace("{{JWT_TOKEN}}", jwt_token)
    html_content = html_content.replace("{{SESSION_ID}}", session_id)
    html_content = html_content.replace("{{SCENARIO_NAME}}", scenario.get('name', 'Unknown'))
    html_content = html_content.replace("{{CHARACTER_NAME}}", character.get('name', 'Unknown'))
    html_content = html_content.replace("{{BASE_URL}}", BASE_URL.replace('http://', 'ws://').replace('https://', 'wss://'))
    
    return html_content

def create_inline_html_template():
    """Create HTML template inline if template file doesn't exist."""
    return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Voice Backend Test - {{SCENARIO_NAME}} with {{CHARACTER_NAME}}</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        h1 { color: #333; margin-top: 0; }
        .info-box {
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 12px;
            margin: 15px 0;
            border-radius: 4px;
        }
        .controls {
            display: flex;
            gap: 10px;
            margin: 20px 0;
            flex-wrap: wrap;
            align-items: center;
        }
        button {
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            background: #007bff;
            color: white;
            cursor: pointer;
            font-size: 14px;
        }
        button:hover { background: #0056b3; }
        button:disabled { background: #ccc; cursor: not-allowed; }
        button.recording {
            background: #dc3545;
            animation: pulse 1.5s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }
        .status {
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
            background: #f0f0f0;
        }
        .status.connected { background: #d4edda; color: #155724; }
        .status.error { background: #f8d7da; color: #721c24; }
        .transcript {
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 10px;
            margin-top: 20px;
            background: #fafafa;
        }
        .message {
            margin: 10px 0;
            padding: 8px 12px;
            border-radius: 4px;
        }
        .message.user {
            background: #e3f2fd;
            margin-left: 20%;
            text-align: right;
        }
        .message.assistant {
            background: #f5f5f5;
            margin-right: 20%;
        }
        .text-input {
            display: flex;
            gap: 10px;
            margin: 20px 0;
        }
        .text-input input {
            flex: 1;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        .config-display {
            background: #f8f9fa;
            padding: 10px;
            border-radius: 4px;
            margin: 10px 0;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎙️ Voice Backend Test</h1>
        
        <div class="info-box">
            <strong>Test Session:</strong> {{SCENARIO_NAME}} with {{CHARACTER_NAME}}<br>
            <strong>Session ID:</strong> {{SESSION_ID}}<br>
            <strong>Status:</strong> Ready to connect
        </div>

        <div class="config-display" id="configDisplay" style="display: none;">
            <strong>Audio Config:</strong> <span id="audioInfo">-</span><br>
            <strong>Language:</strong> <span id="languageInfo">-</span>
        </div>

        <div class="status" id="status">Ready to connect</div>

        <div class="controls">
            <button id="connectBtn" onclick="connect()">🔗 Connect</button>
            <button id="pushToTalkBtn" onmousedown="startRecording()" onmouseup="stopRecording()" onmouseleave="stopRecording()" disabled>
                🎤 Push to Talk
            </button>
            <button id="disconnectBtn" onclick="disconnect()" disabled>🔌 Disconnect</button>
            <span id="recordingInfo" style="margin-left: 10px; color: #666;"></span>
        </div>

        <div class="text-input">
            <input type="text" id="textInput" placeholder="Type a message..." disabled onkeypress="handleKeyPress(event)">
            <button id="sendTextBtn" onclick="sendText()" disabled>📝 Send Text</button>
        </div>

        <div class="transcript" id="transcript">
            <div style="text-align: center; color: #999;">Transcript will appear here...</div>
        </div>
    </div>

    <script>
        // Pre-filled credentials
        const JWT_TOKEN = "{{JWT_TOKEN}}";
        const SESSION_ID = "{{SESSION_ID}}";
        const WS_URL = `{{BASE_URL}}/voice/ws/${SESSION_ID}?token=${JWT_TOKEN}`;
        
        let ws = null;
        let audioContext = null;
        let recorder = null;
        let isRecording = false;

        console.log("Voice Test Configuration:");
        console.log("JWT Token:", JWT_TOKEN.substring(0, 50) + "...");
        console.log("Session ID:", SESSION_ID);
        console.log("WebSocket URL:", WS_URL);

        async function connect() {
            try {
                updateStatus("Connecting...", "");
                ws = new WebSocket(WS_URL);

                ws.onopen = () => {
                    console.log("WebSocket connected");
                    updateStatus("Connected", "connected");
                    document.getElementById("connectBtn").disabled = true;
                    document.getElementById("pushToTalkBtn").disabled = false;
                    document.getElementById("textInput").disabled = false;
                    document.getElementById("sendTextBtn").disabled = false;
                    document.getElementById("disconnectBtn").disabled = false;
                };

                ws.onmessage = (event) => {
                    const message = JSON.parse(event.data);
                    console.log("Received:", message);
                    handleMessage(message);
                };

                ws.onerror = (error) => {
                    console.error("WebSocket error:", error);
                    updateStatus("Connection error", "error");
                };

                ws.onclose = (event) => {
                    console.log("WebSocket closed:", event.code, event.reason);
                    updateStatus(`Disconnected: ${event.reason || "Connection closed"}`, "error");
                    resetUI();
                };
            } catch (error) {
                console.error("Connection failed:", error);
                updateStatus("Connection failed", "error");
            }
        }

        function handleMessage(message) {
            switch (message.type) {
                case "config":
                    displayConfig(message);
                    break;
                case "status":
                    updateStatus(`Server: ${message.status} - ${message.message || ""}`, message.status === "ready" ? "connected" : "");
                    break;
                case "transcript_partial":
                    // Show partial transcript with styling
                    showPartialTranscript(message.text, message.role);
                    break;
                case "transcript_final":
                    // Add final transcript
                    addTranscript(message.text, message.role);
                    break;
                case "audio":
                    // We received audio data (base64)
                    console.log(`Received audio chunk: ${message.data.length} chars`);
                    // Could implement audio playback here
                    break;
                case "turn_status":
                    console.log("Turn status:", message);
                    break;
                case "error":
                    updateStatus(`Error: ${message.error}`, "error");
                    break;
                default:
                    console.log("Unknown message type:", message);
            }
        }

        function displayConfig(config) {
            document.getElementById("configDisplay").style.display = "block";
            document.getElementById("audioInfo").textContent = `${config.audio_format} @ ${config.sample_rate}Hz`;
            document.getElementById("languageInfo").textContent = config.language;
        }

        async function initAudio() {
            try {
                audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                const source = audioContext.createMediaStreamSource(stream);
                const processor = audioContext.createScriptProcessor(4096, 1, 1);

                processor.onaudioprocess = (e) => {
                    if (!isRecording || !ws || ws.readyState !== WebSocket.OPEN) return;
                    
                    const inputData = e.inputBuffer.getChannelData(0);
                    const int16Data = new Int16Array(inputData.length);
                    for (let i = 0; i < inputData.length; i++) {
                        int16Data[i] = Math.max(-32768, Math.min(32767, Math.floor(inputData[i] * 32768)));
                    }
                    
                    const base64Audio = btoa(String.fromCharCode(...new Uint8Array(int16Data.buffer)));
                    const message = {
                        mime_type: "audio/pcm",
                        data: base64Audio,
                        end_session: false
                    };
                    ws.send(JSON.stringify(message));
                };

                source.connect(processor);
                processor.connect(audioContext.destination);
                recorder = { source, processor, stream };
                return true;
            } catch (error) {
                console.error("Audio init failed:", error);
                updateStatus(`Microphone error: ${error.message}`, "error");
                return false;
            }
        }

        async function startRecording() {
            if (!recorder && !(await initAudio())) return;
            
            isRecording = true;
            document.getElementById("pushToTalkBtn").classList.add("recording");
            document.getElementById("recordingInfo").textContent = "🔴 Recording...";
        }

        function stopRecording() {
            isRecording = false;
            document.getElementById("pushToTalkBtn").classList.remove("recording");
            document.getElementById("recordingInfo").textContent = "";
        }

        function sendText() {
            const input = document.getElementById("textInput");
            const text = input.value.trim();
            if (!text || !ws || ws.readyState !== WebSocket.OPEN) return;

            const message = {
                mime_type: "text/plain",
                data: btoa(unescape(encodeURIComponent(text))),
                end_session: false
            };
            
            ws.send(JSON.stringify(message));
            addTranscript(text, "user");
            input.value = "";
        }

        function handleKeyPress(event) {
            if (event.key === "Enter") sendText();
        }

        function disconnect() {
            if (ws) {
                // Send end session message
                const endMsg = {
                    mime_type: "text/plain", 
                    data: "",
                    end_session: true
                };
                ws.send(JSON.stringify(endMsg));
                ws.close();
            }
            resetUI();
        }

        function resetUI() {
            document.getElementById("connectBtn").disabled = false;
            document.getElementById("pushToTalkBtn").disabled = true;
            document.getElementById("textInput").disabled = true;
            document.getElementById("sendTextBtn").disabled = true;
            document.getElementById("disconnectBtn").disabled = true;
            document.getElementById("recordingInfo").textContent = "";
            document.getElementById("configDisplay").style.display = "none";
        }

        function updateStatus(message, type = "") {
            const statusEl = document.getElementById("status");
            statusEl.textContent = message;
            statusEl.className = "status " + type;
        }

        function addTranscript(text, role) {
            const transcriptEl = document.getElementById("transcript");
            
            if (transcriptEl.querySelector('div[style*="text-align: center"]')) {
                transcriptEl.innerHTML = "";
            }

            const messageEl = document.createElement("div");
            messageEl.className = `message ${role}`;
            messageEl.textContent = text;
            transcriptEl.appendChild(messageEl);
            transcriptEl.scrollTop = transcriptEl.scrollHeight;
        }

        let partialElement = null;
        function showPartialTranscript(text, role) {
            const transcriptEl = document.getElementById("transcript");
            
            if (!partialElement || partialElement.className !== `message ${role} partial`) {
                // Create new partial element
                partialElement = document.createElement("div");
                partialElement.className = `message ${role} partial`;
                partialElement.style.opacity = "0.7";
                partialElement.style.fontStyle = "italic";
                transcriptEl.appendChild(partialElement);
            }
            
            partialElement.textContent = text + " ...";
            transcriptEl.scrollTop = transcriptEl.scrollHeight;
        }

        // Cleanup on page unload
        window.addEventListener("beforeunload", () => {
            if (ws) ws.close();
            if (recorder && recorder.stream) {
                recorder.stream.getTracks().forEach(track => track.stop());
            }
        });
    </script>
</body>
</html>'''

async def main():
    parser = argparse.ArgumentParser(description='Setup voice testing session')
    parser.add_argument('--user', default='test@example.com', help='Login email')
    parser.add_argument('--password', default='password', help='Login password')
    args = parser.parse_args()
    
    success = await create_voice_test_session(args.user, args.password)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())