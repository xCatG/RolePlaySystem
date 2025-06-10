/**
 * Composable for managing async operations with loading and error states
 * Eliminates duplicate loading/error patterns across components
 */
import { ref } from 'vue'

export function useAsyncOperation() {
  const loading = ref(false)
  const error = ref('')

  const withLoading = async <T>(fn: () => Promise<T>): Promise<T | null> => {
    try {
      loading.value = true
      error.value = ''
      return await fn()
    } catch (err: any) {
      error.value = err.message || 'An error occurred'
      console.error('Async operation failed:', err)
      return null
    } finally {
      loading.value = false
    }
  }

  const clearError = () => {
    error.value = ''
  }

  return {
    loading,
    error,
    withLoading,
    clearError
  }
}