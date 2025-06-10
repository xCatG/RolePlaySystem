/**
 * Composable for centralized chat data management
 * Eliminates duplicate data loading and state management
 */
import { ref, computed } from 'vue'
import { chatApi } from '../services'
import { useAsyncOperation } from './useAsyncOperation'
import type { ScenarioInfo, CharacterInfo, SessionInfo } from '../types/chat'

export function useChatData() {
  const { withLoading } = useAsyncOperation()
  
  // Core data
  const scenarios = ref<ScenarioInfo[]>([])
  const characters = ref<CharacterInfo[]>([])
  const sessions = ref<SessionInfo[]>([])
  
  // Selection state
  const selectedScenarioId = ref('')
  const selectedCharacterId = ref('')
  
  // Computed values
  const selectedScenario = computed(() => 
    scenarios.value.find(s => s.id === selectedScenarioId.value)
  )
  
  const selectedCharacter = computed(() =>
    characters.value.find(c => c.id === selectedCharacterId.value)
  )

  // Data loading methods
  const loadScenarios = async (language?: string) => {
    const result = await withLoading(() => chatApi.getScenarios(language))
    if (result?.scenarios) {
      scenarios.value = result.scenarios
    }
  }

  const loadCharacters = async (scenarioId: string, language?: string) => {
    if (!scenarioId) {
      characters.value = []
      return
    }
    
    const result = await withLoading(() => chatApi.getCharacters(scenarioId, language))
    if (result?.characters) {
      characters.value = result.characters
    }
  }

  const loadSessions = async () => {
    const result = await withLoading(() => chatApi.getSessions())
    if (result?.sessions) {
      sessions.value = result.sessions
    }
  }

  // Refresh all data
  const refreshData = async (language?: string) => {
    await Promise.all([
      loadScenarios(language),
      loadSessions()
    ])
    
    // Reload characters if scenario is selected
    if (selectedScenarioId.value) {
      await loadCharacters(selectedScenarioId.value, language)
    }
  }

  // Reset selection state
  const resetSelections = () => {
    selectedScenarioId.value = ''
    selectedCharacterId.value = ''
    characters.value = []
  }

  return {
    // Data
    scenarios,
    characters,
    sessions,
    
    // Selection
    selectedScenarioId,
    selectedCharacterId,
    selectedScenario,
    selectedCharacter,
    
    // Methods
    loadScenarios,
    loadCharacters,
    loadSessions,
    refreshData,
    resetSelections
  }
}