/**
 * Composable for managing voice WebSocket connections with audio streaming.
 */

import { ref, onUnmounted } from 'vue'
import type { 
  VoiceStatus, 
  PartialTranscript, 
  FinalTranscript,
  VoiceConfig,
  AudioChunk,
  TurnStatus
} from '../types/voice'

interface VoiceWebSocketConfig {
  sessionId: string
  token: string
  onPartialTranscript?: (transcript: PartialTranscript) => void
  onFinalTranscript?: (transcript: FinalTranscript) => void
  onAudioChunk?: (chunk: AudioChunk) => void
  onTurnStatus?: (status: TurnStatus) => void
  onStatusChange?: (status: VoiceStatus) => void
  onError?: (error: string) => void
}

export function useVoiceWebSocket(config: VoiceWebSocketConfig) {
  // State
  const isConnected = ref(false)
  const isConnecting = ref(false)
  const isRecording = ref(false)
  const canRecord = ref(false)
  const connectionStatus = ref<VoiceStatus | null>(null)
  const voiceConfig = ref<VoiceConfig | null>(null)

  // WebSocket and audio references
  let websocket: WebSocket | null = null
  let mediaRecorder: MediaRecorder | null = null
  let audioContext: AudioContext | null = null
  let audioWorkletNode: AudioWorkletNode | null = null
  let audioStream: MediaStream | null = null
  let audioQueue: Float32Array[] = []
  let isPlaying = ref(false)

  // Audio configuration
  const SAMPLE_RATE = 16000
  const CHANNELS = 1
  const CHUNK_SIZE = 1600 // 100ms at 16kHz

  // WebSocket connection
  const connect = async (): Promise<void> => {
    if (isConnected.value || isConnecting.value) {
      return
    }

    isConnecting.value = true
    connectionStatus.value = {
      type: 'connecting',
      message: 'Connecting to voice service...',
      timestamp: new Date().toISOString()
    }

    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const host = window.location.host
      const wsUrl = `${protocol}//${host}/api/voice/ws/${config.sessionId}?token=${config.token}`
      
      websocket = new WebSocket(wsUrl)
      
      websocket.onopen = () => {
        isConnected.value = true
        isConnecting.value = false
        connectionStatus.value = {
          type: 'connected',
          message: 'Connected to voice service',
          timestamp: new Date().toISOString()
        }
        config.onStatusChange?.(connectionStatus.value)
      }

      websocket.onmessage = async (event) => {
        try {
          const message = JSON.parse(event.data)
          await handleWebSocketMessage(message)
        } catch (error) {
          console.error('Error parsing WebSocket message:', error)
        }
      }

      websocket.onclose = (event) => {
        isConnected.value = false
        isConnecting.value = false
        isRecording.value = false
        canRecord.value = false
        
        connectionStatus.value = {
          type: 'disconnected',
          message: `Connection closed: ${event.reason || 'Unknown reason'}`,
          timestamp: new Date().toISOString()
        }
        config.onStatusChange?.(connectionStatus.value)
        
        cleanup()
      }

      websocket.onerror = (error) => {
        console.error('WebSocket error:', error)
        connectionStatus.value = {
          type: 'error',
          message: 'Connection error occurred',
          timestamp: new Date().toISOString()
        }
        config.onError?.('WebSocket connection failed')
        config.onStatusChange?.(connectionStatus.value)
      }

    } catch (error) {
      isConnecting.value = false
      connectionStatus.value = {
        type: 'error',
        message: `Failed to connect: ${error}`,
        timestamp: new Date().toISOString()
      }
      config.onError?.(`Connection failed: ${error}`)
      config.onStatusChange?.(connectionStatus.value)
      throw error
    }
  }

  // Handle incoming WebSocket messages
  const handleWebSocketMessage = async (message: any) => {
    switch (message.type) {
      case 'config':
        voiceConfig.value = message as VoiceConfig
        await initializeAudio()
        break
        
      case 'status':
        if (message.status === 'ready') {
          canRecord.value = true
        }
        connectionStatus.value = {
          type: message.status,
          message: message.message,
          timestamp: message.timestamp
        }
        config.onStatusChange?.(connectionStatus.value)
        break
        
      case 'transcript_partial':
        config.onPartialTranscript?.(message as PartialTranscript)
        break
        
      case 'transcript_final':
        config.onFinalTranscript?.(message as FinalTranscript)
        break
        
      case 'audio':
        await playAudioChunk(message as AudioChunk)
        config.onAudioChunk?.(message as AudioChunk)
        break
        
      case 'turn_status':
        config.onTurnStatus?.(message as TurnStatus)
        break
        
      case 'error':
        config.onError?.(message.error)
        connectionStatus.value = {
          type: 'error',
          message: message.error,
          timestamp: message.timestamp
        }
        config.onStatusChange?.(connectionStatus.value)
        break
    }
  }

  // Initialize audio context and worklet
  const initializeAudio = async () => {
    try {
      // Initialize AudioContext for playback
      audioContext = new AudioContext({ sampleRate: SAMPLE_RATE })
      
      // Resume context if suspended (required for user interaction)
      if (audioContext.state === 'suspended') {
        await audioContext.resume()
      }

      console.log('Audio initialized:', {
        sampleRate: audioContext.sampleRate,
        state: audioContext.state
      })
      
    } catch (error) {
      console.error('Failed to initialize audio:', error)
      config.onError?.(`Audio initialization failed: ${error}`)
    }
  }

  // Start audio recording
  const startRecording = async (): Promise<void> => {
    if (!canRecord.value || isRecording.value) {
      return
    }

    try {
      // Request microphone access
      audioStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: SAMPLE_RATE,
          channelCount: CHANNELS,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true
        }
      })

      // Create MediaRecorder for capturing audio
      const options = {
        mimeType: 'audio/webm;codecs=opus', // Fallback to available format
        audioBitsPerSecond: 16000
      }
      
      // Find a supported MIME type
      const supportedTypes = [
        'audio/webm;codecs=opus',
        'audio/webm',
        'audio/mp4',
        'audio/wav'
      ]
      
      const mimeType = supportedTypes.find(type => MediaRecorder.isTypeSupported(type))
      if (mimeType) {
        options.mimeType = mimeType
      }

      mediaRecorder = new MediaRecorder(audioStream, options)
      let audioChunks: Blob[] = []

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data)
        }
      }

      mediaRecorder.onstop = async () => {
        if (audioChunks.length > 0) {
          const audioBlob = new Blob(audioChunks, { type: options.mimeType })
          await sendAudioBlob(audioBlob)
          audioChunks = []
        }
      }

      // Start recording in chunks
      mediaRecorder.start(100) // Record in 100ms chunks
      isRecording.value = true

      console.log('Recording started')

    } catch (error) {
      console.error('Failed to start recording:', error)
      config.onError?.(`Recording failed: ${error}`)
      throw error
    }
  }

  // Stop audio recording
  const stopRecording = async (): Promise<void> => {
    if (!isRecording.value || !mediaRecorder) {
      return
    }

    try {
      mediaRecorder.stop()
      isRecording.value = false
      
      // Stop all tracks to release microphone
      if (audioStream) {
        audioStream.getTracks().forEach(track => track.stop())
        audioStream = null
      }
      
      console.log('Recording stopped')
      
    } catch (error) {
      console.error('Failed to stop recording:', error)
      config.onError?.(`Failed to stop recording: ${error}`)
    }
  }

  // Convert audio blob to PCM and send
  const sendAudioBlob = async (blob: Blob): Promise<void> => {
    if (!websocket || websocket.readyState !== WebSocket.OPEN) {
      return
    }

    try {
      // Convert blob to array buffer
      const arrayBuffer = await blob.arrayBuffer()
      
      // For now, send the raw audio data
      // In production, you'd want to convert to PCM format
      const base64Data = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)))
      
      const audioMessage = {
        mime_type: 'audio/pcm',
        data: base64Data,
        end_session: false
      }

      websocket.send(JSON.stringify(audioMessage))
      
    } catch (error) {
      console.error('Failed to send audio:', error)
      config.onError?.(`Failed to send audio: ${error}`)
    }
  }

  // Send text message
  const sendTextMessage = async (text: string): Promise<void> => {
    if (!websocket || websocket.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket not connected')
    }

    try {
      const textMessage = {
        mime_type: 'text/plain',
        data: btoa(text),
        end_session: false
      }

      websocket.send(JSON.stringify(textMessage))
      
    } catch (error) {
      console.error('Failed to send text:', error)
      config.onError?.(`Failed to send text: ${error}`)
      throw error
    }
  }

  // Play audio chunk
  const playAudioChunk = async (audioChunk: AudioChunk): Promise<void> => {
    if (!audioContext) {
      return
    }

    try {
      // Decode base64 audio data
      const audioData = atob(audioChunk.data)
      const audioBuffer = new ArrayBuffer(audioData.length)
      const audioView = new Uint8Array(audioBuffer)
      
      for (let i = 0; i < audioData.length; i++) {
        audioView[i] = audioData.charCodeAt(i)
      }

      // Decode audio buffer
      const decodedBuffer = await audioContext.decodeAudioData(audioBuffer)
      
      // Create buffer source and play
      const source = audioContext.createBufferSource()
      source.buffer = decodedBuffer
      source.connect(audioContext.destination)
      source.start()

    } catch (error) {
      console.error('Failed to play audio chunk:', error)
      // Don't throw here, just log the error to avoid breaking the flow
    }
  }

  // Disconnect WebSocket
  const disconnect = async (): Promise<void> => {
    if (isRecording.value) {
      await stopRecording()
    }

    if (websocket) {
      // Send end session message
      try {
        if (websocket.readyState === WebSocket.OPEN) {
          const endMessage = {
            mime_type: 'text/plain',
            data: '',
            end_session: true
          }
          websocket.send(JSON.stringify(endMessage))
        }
      } catch (error) {
        console.error('Failed to send end session message:', error)
      }

      websocket.close()
      websocket = null
    }

    cleanup()
  }

  // Cleanup resources
  const cleanup = () => {
    isConnected.value = false
    isConnecting.value = false
    isRecording.value = false
    canRecord.value = false

    if (audioStream) {
      audioStream.getTracks().forEach(track => track.stop())
      audioStream = null
    }

    if (audioContext) {
      audioContext.close()
      audioContext = null
    }

    mediaRecorder = null
    audioWorkletNode = null
    audioQueue = []
  }

  // Cleanup on unmount
  onUnmounted(() => {
    disconnect()
  })

  return {
    // State
    isConnected: readonly(isConnected),
    isConnecting: readonly(isConnecting),
    isRecording: readonly(isRecording),
    canRecord: readonly(canRecord),
    connectionStatus: readonly(connectionStatus),
    voiceConfig: readonly(voiceConfig),
    isPlaying: readonly(isPlaying),

    // Methods
    connect,
    disconnect,
    startRecording,
    stopRecording,
    sendTextMessage
  }
}