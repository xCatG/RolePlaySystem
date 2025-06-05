import { createApp } from 'vue'
import { createI18n } from 'vue-i18n'
import App from './App.vue'
import messages from './locales'

// Create i18n instance
const i18n = createI18n({
  legacy: false,
  locale: localStorage.getItem('language') || 'en',
  fallbackLocale: 'en',
  messages
})

const app = createApp(App)
app.use(i18n)
app.mount('#app')
