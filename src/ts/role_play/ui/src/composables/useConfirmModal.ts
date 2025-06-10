/**
 * Composable for managing confirmation modals
 * Eliminates duplicate modal management patterns across components
 */
import { ref } from 'vue'

export function useConfirmModal() {
  const showModal = ref(false)
  const pendingAction = ref<(() => Promise<void>) | null>(null)
  const currentTitle = ref('')
  const currentMessage = ref('')

  const confirm = async (
    action: () => Promise<void>,
    title: string = 'Confirm Action',
    message: string = 'Are you sure you want to proceed?'
  ) => {
    pendingAction.value = action
    currentTitle.value = title
    currentMessage.value = message
    showModal.value = true
  }

  const execute = async () => {
    if (pendingAction.value) {
      await pendingAction.value()
    }
    reset()
  }

  const reset = () => {
    showModal.value = false
    pendingAction.value = null
    currentTitle.value = ''
    currentMessage.value = ''
  }

  return {
    showModal,
    title: currentTitle,
    message: currentMessage,
    confirm,
    execute,
    cancel: reset
  }
}