/**
 * Composable for session management actions (end, delete)
 * Centralizes session operations and eliminates duplication
 */
import { chatApi } from '../services'
import { useAsyncOperation } from './useAsyncOperation'
import { useConfirmModal } from './useConfirmModal'
import { useI18n } from 'vue-i18n'

export function useSessionActions() {
  const { withLoading } = useAsyncOperation()
  const { confirm } = useConfirmModal()
  const { t } = useI18n()

  const endSession = async (sessionId: string, onSuccess?: () => void) => {
    await confirm(
      async () => {
        const result = await withLoading(() => chatApi.endSession(sessionId))
        if (result && onSuccess) {
          onSuccess()
        }
      },
      t('sessionActions.endSessionTitle'),
      t('sessionActions.endSessionMessage')
    )
  }

  const deleteSession = async (sessionId: string, onSuccess?: () => void) => {
    await confirm(
      async () => {
        const result = await withLoading(() => chatApi.deleteSession(sessionId))
        if (result && onSuccess) {
          onSuccess()
        }
      },
      t('sessionActions.deleteSessionTitle'),
      t('sessionActions.deleteSessionMessage')
    )
  }

  return {
    endSession,
    deleteSession
  }
}