<template>
  <div class="language-switcher">
    <label for="language-select" class="language-label">
      {{ $t('nav.languageSwitch') }}:
    </label>
    <select 
      id="language-select"
      v-model="currentLanguage" 
      @change="requestLanguageChange"
      class="language-select"
    >
      <option value="en">English</option>
      <option value="zh-TW">繁體中文</option>
    </select>
    
    <!-- Confirmation Modal -->
    <ConfirmModal
      v-model="showConfirmModal"
      :message="$t('warnings.languageSwitch')"
      @confirm="confirmLanguageChange"
      @cancel="cancelLanguageChange"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import ConfirmModal from './ConfirmModal.vue'
import { userApi } from '../services/userApi'

const emit = defineEmits<{
  'language-changed': [language: string]
}>()

const { locale, t } = useI18n()

const currentLanguage = ref(locale.value)
const pendingLanguage = ref<string | null>(null)
const showConfirmModal = ref(false)

onMounted(() => {
  // Initialize with stored language preference
  const savedLanguage = localStorage.getItem('language')
  if (savedLanguage && savedLanguage !== locale.value) {
    currentLanguage.value = savedLanguage
    locale.value = savedLanguage
  }
})

const requestLanguageChange = () => {
  // If same language, do nothing
  if (currentLanguage.value === locale.value) {
    return
  }
  
  // Store the pending change and show confirmation
  pendingLanguage.value = currentLanguage.value
  showConfirmModal.value = true
}

const confirmLanguageChange = async () => {
  if (!pendingLanguage.value) return
  
  try {
    // Update i18n locale
    locale.value = pendingLanguage.value
    
    // Store in localStorage
    localStorage.setItem('language', pendingLanguage.value)
    
    // Update backend user preference
    await userApi.updateLanguagePreference(pendingLanguage.value)
    
    // Emit event to trigger content reload
    emit('language-changed', pendingLanguage.value)
    
    pendingLanguage.value = null
  } catch (error) {
    console.error('Failed to update language preference:', error)
    // Revert the UI selection on failure
    currentLanguage.value = locale.value
    // Show error message (you might want to emit an error event here)
    alert(t('errors.updateLanguageFailed'))
  }
}

const cancelLanguageChange = () => {
  // Revert the select value
  currentLanguage.value = locale.value
  pendingLanguage.value = null
}
</script>

<style scoped>
.language-switcher {
  display: flex;
  align-items: center;
  gap: 8px;
}

.language-label {
  font-size: 0.875rem;
  color: #495057;
  font-weight: 500;
}

.language-select {
  padding: 4px 8px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  font-size: 0.875rem;
  background-color: white;
  cursor: pointer;
  transition: border-color 0.2s;
}

.language-select:focus {
  outline: none;
  border-color: #007bff;
  box-shadow: 0 0 0 2px rgba(0, 123, 255, 0.1);
}

.language-select:hover {
  border-color: #adb5bd;
}

/* Mobile responsive */
@media (max-width: 767px) {
  .language-switcher {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }
  
  .language-select {
    width: 100%;
  }
}
</style>
