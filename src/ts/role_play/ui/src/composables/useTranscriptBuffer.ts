/**
 * Composable for managing transcript buffering on the frontend.
 * Mirrors the backend transcript management logic for consistent UX.
 */

import { ref, computed } from 'vue'
import type { TranscriptMessage, PartialTranscript, FinalTranscript } from '../types/voice'

interface TranscriptBufferConfig {
  stabilityThreshold?: number
  maxPartialAge?: number // milliseconds
}

export function useTranscriptBuffer(config: TranscriptBufferConfig = {}) {
  const {
    stabilityThreshold = 0.8,
    maxPartialAge = 5000 // 5 seconds
  } = config

  // State
  const finalMessages = ref<TranscriptMessage[]>([])
  const partialMessage = ref<PartialTranscript | null>(null)
  const messageCounter = ref(0)

  // Computed
  const hasMessages = computed(() => finalMessages.value.length > 0)
  const displayText = computed(() => {
    const finalText = finalMessages.value.map(m => m.text).join(' ')
    const partialText = partialMessage.value?.text || ''
    return [finalText, partialText].filter(Boolean).join(' ')
  })

  // Methods
  const addPartialTranscript = (partial: PartialTranscript) => {
    // Update partial message for live display
    partialMessage.value = {
      ...partial,
      timestamp: partial.timestamp || new Date().toISOString()
    }

    // Clean up old partial if it's been too long
    if (partialMessage.value) {
      const age = Date.now() - new Date(partialMessage.value.timestamp).getTime()
      if (age > maxPartialAge) {
        partialMessage.value = null
      }
    }
  }

  const addFinalTranscript = (final: FinalTranscript) => {
    // Clear any partial message for this role
    if (partialMessage.value && partialMessage.value.role === final.role) {
      partialMessage.value = null
    }

    // Add to final messages
    const message: TranscriptMessage = {
      id: `msg-${Date.now()}-${messageCounter.value++}`,
      text: final.text,
      role: final.role,
      timestamp: final.timestamp || new Date().toISOString(),
      isVoice: true,
      duration: final.duration_ms,
      confidence: final.confidence,
      metadata: final.metadata || {}
    }

    finalMessages.value.push(message)

    // Keep only recent messages to prevent memory bloat
    if (finalMessages.value.length > 100) {
      finalMessages.value = finalMessages.value.slice(-80) // Keep last 80 messages
    }
  }

  const addTextMessage = (text: string, role: 'user' | 'assistant') => {
    const message: TranscriptMessage = {
      id: `text-${Date.now()}-${messageCounter.value++}`,
      text,
      role,
      timestamp: new Date().toISOString(),
      isVoice: false
    }

    finalMessages.value.push(message)
  }

  const updatePartialStability = (stability: number) => {
    if (partialMessage.value) {
      partialMessage.value.stability = stability
    }
  }

  const clear = () => {
    finalMessages.value = []
    partialMessage.value = null
    messageCounter.value = 0
  }

  const getMessageById = (id: string): TranscriptMessage | undefined => {
    return finalMessages.value.find(m => m.id === id)
  }

  const getMessagesInRange = (startTime: string, endTime: string): TranscriptMessage[] => {
    const start = new Date(startTime).getTime()
    const end = new Date(endTime).getTime()
    
    return finalMessages.value.filter(message => {
      const msgTime = new Date(message.timestamp).getTime()
      return msgTime >= start && msgTime <= end
    })
  }

  const exportTranscript = (): string => {
    const lines = finalMessages.value.map(message => {
      const timestamp = new Date(message.timestamp).toLocaleTimeString()
      const roleLabel = message.role === 'user' ? 'You' : 'Character'
      const voiceLabel = message.isVoice ? ' [Voice]' : ''
      const durationLabel = message.duration ? ` (${(message.duration / 1000).toFixed(1)}s)` : ''
      
      return `[${timestamp}] ${roleLabel}${voiceLabel}${durationLabel}: ${message.text}`
    })
    
    return lines.join('\n')
  }

  const getStatistics = () => {
    const totalMessages = finalMessages.value.length
    const voiceMessages = finalMessages.value.filter(m => m.isVoice).length
    const textMessages = totalMessages - voiceMessages
    const averageConfidence = finalMessages.value
      .filter(m => m.confidence !== undefined)
      .reduce((sum, m) => sum + (m.confidence || 0), 0) / voiceMessages || 0
    
    const totalDuration = finalMessages.value
      .filter(m => m.duration !== undefined)
      .reduce((sum, m) => sum + (m.duration || 0), 0)

    return {
      totalMessages,
      voiceMessages,
      textMessages,
      averageConfidence: Math.round(averageConfidence * 100) / 100,
      totalDurationMs: totalDuration,
      totalDurationSeconds: Math.round(totalDuration / 1000 * 10) / 10
    }
  }

  // Auto-cleanup for old partial messages
  let partialCleanupInterval: NodeJS.Timeout | null = null
  
  const startPartialCleanup = () => {
    if (partialCleanupInterval) return
    
    partialCleanupInterval = setInterval(() => {
      if (partialMessage.value) {
        const age = Date.now() - new Date(partialMessage.value.timestamp).getTime()
        if (age > maxPartialAge) {
          partialMessage.value = null
        }
      }
    }, 1000) // Check every second
  }

  const stopPartialCleanup = () => {
    if (partialCleanupInterval) {
      clearInterval(partialCleanupInterval)
      partialCleanupInterval = null
    }
  }

  // Start cleanup on initialization
  startPartialCleanup()

  return {
    // State
    finalMessages: readonly(finalMessages),
    partialMessage: readonly(partialMessage),
    
    // Computed
    hasMessages,
    displayText,
    
    // Methods
    addPartialTranscript,
    addFinalTranscript,
    addTextMessage,
    updatePartialStability,
    clear,
    getMessageById,
    getMessagesInRange,
    exportTranscript,
    getStatistics,
    
    // Lifecycle
    startPartialCleanup,
    stopPartialCleanup
  }
}