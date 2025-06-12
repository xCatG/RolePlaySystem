<template>
  <div class="app">
    <!-- Navigation Header -->
    <header class="app-header">
      <div class="header-content">
        <h1 class="app-title">{{ $t('nav.title') }}</h1>
        
        <!-- Desktop Navigation -->
        <nav v-if="user" class="desktop-nav">
          <LanguageSwitcher :token="token" @language-changed="handleLanguageChange" />
          <div class="user-info">
            <span class="user-name">{{ user.username }}</span>
            <span class="user-role">{{ user.role }}</span>
          </div>
          <div class="nav-actions">
            <button @click="logout" class="logout-btn">{{ $t('auth.logout') }}</button>
          </div>
        </nav>
        
        <!-- Mobile Navigation Toggle -->
        <button v-if="user" @click="toggleMobileMenu" class="mobile-menu-toggle">
          <span class="hamburger-line"></span>
          <span class="hamburger-line"></span>
          <span class="hamburger-line"></span>
        </button>
      </div>
      
      <!-- Mobile Menu -->
      <div v-if="user && showMobileMenu" class="mobile-menu">
        <div class="mobile-language-switcher">
          <LanguageSwitcher @language-changed="handleLanguageChange" />
        </div>
        <div class="mobile-user-info">
          <div class="user-details">
            <strong>{{ user.username }}</strong>
            <p>{{ user.email }}</p>
            <span class="role-badge">{{ user.role }}</span>
          </div>
        </div>
        <div class="mobile-actions">
          <button @click="logout" class="mobile-logout-btn">{{ $t('auth.logout') }}</button>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="main-content">
      <!-- Logged in view -->
      <div v-if="user">
        <!-- Chat Component -->
        <Chat ref="chatComponent" />
      </div>
    
      <!-- Login/Register view -->
      <div v-else class="auth-container">
        <div class="auth-card">
          <div class="tabs">
            <button 
              class="tab" 
              :class="{ active: activeTab === 'login' }"
              @click="activeTab = 'login'"
            >
              {{ $t('auth.login') }}
            </button>
            <button 
              class="tab" 
              :class="{ active: activeTab === 'register' }"
              @click="activeTab = 'register'"
            >
              {{ $t('auth.register') }}
            </button>
          </div>

          <!-- Login Form -->
          <form v-if="activeTab === 'login'" @submit.prevent="login">
            <div class="form-group">
              <label for="login-email">{{ $t('auth.email') }}:</label>
              <input 
                id="login-email"
                v-model="loginForm.email" 
                type="email" 
                required 
                :disabled="loading"
              />
            </div>
            <div class="form-group">
              <label for="login-password">{{ $t('auth.password') }}:</label>
              <input 
                id="login-password"
                v-model="loginForm.password" 
                type="password" 
                required 
                :disabled="loading"
              />
            </div>
            <button type="submit" :disabled="loading" class="auth-button">
              {{ loading ? $t('auth.loggingIn') : $t('auth.login') }}
            </button>
          </form>

          <!-- Register Form -->
          <form v-if="activeTab === 'register'" @submit.prevent="register">
            <div class="form-group">
              <label for="register-username">{{ $t('auth.username') }}:</label>
              <input 
                id="register-username"
                v-model="registerForm.username" 
                type="text" 
                required 
                :disabled="loading"
              />
            </div>
            <div class="form-group">
              <label for="register-email">{{ $t('auth.email') }}:</label>
              <input 
                id="register-email"
                v-model="registerForm.email" 
                type="email" 
                required 
                :disabled="loading"
              />
            </div>
            <div class="form-group">
              <label for="register-password">{{ $t('auth.password') }}:</label>
              <input 
                id="register-password"
                v-model="registerForm.password" 
                type="password" 
                required 
                :disabled="loading"
                minlength="8"
              />
            </div>
            <button type="submit" :disabled="loading" class="auth-button">
              {{ loading ? $t('auth.registering') : $t('auth.register') }}
            </button>
          </form>

          <!-- Error/Success Messages -->
          <div v-if="error" class="error">{{ error }}</div>
          <div v-if="success" class="success">{{ success }}</div>
        </div>
        
      </div>
    </main>
    
    <!-- Version Info always visible at bottom -->
    <VersionInfo class="version-fixed" />
  </div>
</template>

<script>
import Chat from './components/Chat.vue'
import LanguageSwitcher from './components/LanguageSwitcher.vue'
import VersionInfo from './components/VersionInfo.vue'
import { authApi } from './services/authApi'
import { useI18n } from 'vue-i18n'

export default {
  name: 'App',
  components: {
    Chat,
    LanguageSwitcher,
    VersionInfo
  },
  setup() {
    const { t, locale } = useI18n()
    return { t, locale }
  },
  data() {
    return {
      activeTab: 'login',
      loading: false,
      error: '',
      success: '',
      user: null,
      token: localStorage.getItem('token'),
      showMobileMenu: false,
      loginForm: {
        email: '',
        password: ''
      },
      registerForm: {
        username: '',
        email: '',
        password: ''
      }
    }
  },
  
  async mounted() {
    // Check if user is already logged in
    if (this.token) {
      await this.getCurrentUser()
    }
  },
  
  methods: {
    async login() {
      this.loading = true
      this.error = ''
      this.success = ''
      
      try {
        const response = await authApi.login({
          email: this.loginForm.email,
          password: this.loginForm.password
        })

        this.token = response.access_token
        this.user = response.user
        localStorage.setItem('token', this.token)
        // Sync UI language with user's preferred language
        this.locale = response.user.preferred_language
        localStorage.setItem('language', response.user.preferred_language)

        this.success = this.t('auth.loginSuccess')
        this.loginForm = { email: '', password: '' }
        
      } catch (error) {
        this.error = error.response?.data?.detail || this.t('auth.loginFailed')
      } finally {
        this.loading = false
      }
    },
    
    async register() {
      this.loading = true
      this.error = ''
      this.success = ''
      
      try {
        const response = await authApi.register({
          username: this.registerForm.username,
          email: this.registerForm.email,
          password: this.registerForm.password,
          preferred_language: this.locale
        })

        this.token = response.access_token
        this.user = response.user
        localStorage.setItem('token', this.token)
        // Ensure UI language matches newly registered preference
        this.locale = response.user.preferred_language
        localStorage.setItem('language', response.user.preferred_language)

        this.success = this.t('auth.registerSuccess')
        this.registerForm = { username: '', email: '', password: '' }
        
      } catch (error) {
        this.error = error.response?.data?.detail || this.t('auth.registerFailed')
      } finally {
        this.loading = false
      }
    },
    
    async getCurrentUser() {
      try {
        const user = await authApi.getCurrentUser(this.token)
        this.user = user
        // Apply stored preference to UI when token login succeeds
        this.locale = user.preferred_language
        localStorage.setItem('language', user.preferred_language)
      } catch (error) {
        // Token is invalid, remove it
        this.logout()
      }
    },
    
    logout() {
      this.user = null
      this.token = null
      this.showMobileMenu = false
      localStorage.removeItem('token')
      this.success = this.t('auth.logoutSuccess')
      this.error = ''
    },
    
    toggleMobileMenu() {
      this.showMobileMenu = !this.showMobileMenu
    },
    
    handleLanguageChange(newLanguage) {
      // Close mobile menu if open
      this.showMobileMenu = false
      
      // Update user object with new language preference
      if (this.user) {
        this.user.preferred_language = newLanguage
      }
      
      // Trigger chat component to reload content
      if (this.$refs.chatComponent) {
        this.$refs.chatComponent.handleLanguageChange()
      }
    }
  }
}
</script>

<style>
/* Global Styles */
* {
  box-sizing: border-box;
}

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', sans-serif;
  background-color: #f8f9fa;
}

.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* Header Styles */
.app-header {
  background: white;
  border-bottom: 1px solid #e9ecef;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  position: sticky;
  top: 0;
  z-index: 100;
}

.header-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 0 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  height: 64px;
}

.app-title {
  margin: 0;
  font-size: 1.5rem;
  color: #212529;
  font-weight: 600;
}

/* Desktop Navigation */
.desktop-nav {
  display: none;
  align-items: center;
  gap: 20px;
}

.desktop-nav > * {
  flex-shrink: 0;
}

.user-info {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.user-name {
  font-weight: 600;
  color: #212529;
}

.user-role {
  font-size: 0.875rem;
  color: #6c757d;
  text-transform: capitalize;
}

.logout-btn {
  background-color: #dc3545;
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.875rem;
  font-weight: 500;
  transition: background-color 0.2s;
}

.logout-btn:hover {
  background-color: #c82333;
}

/* Mobile Menu Toggle */
.mobile-menu-toggle {
  display: flex;
  flex-direction: column;
  justify-content: space-around;
  width: 24px;
  height: 24px;
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0;
}

.hamburger-line {
  width: 100%;
  height: 2px;
  background-color: #212529;
  transition: all 0.3s;
}

/* Mobile Menu */
.mobile-menu {
  display: block;
  background: white;
  border-top: 1px solid #e9ecef;
  padding: 20px;
}

.mobile-language-switcher {
  margin-bottom: 20px;
  padding-bottom: 15px;
  border-bottom: 1px solid #e9ecef;
}

.mobile-user-info {
  margin-bottom: 20px;
}

.user-details strong {
  display: block;
  font-size: 1.125rem;
  margin-bottom: 5px;
}

.user-details p {
  margin: 0 0 10px 0;
  color: #6c757d;
  font-size: 0.875rem;
}

.role-badge {
  display: inline-block;
  background: #e9ecef;
  color: #495057;
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 500;
  text-transform: capitalize;
}

.mobile-logout-btn {
  background-color: #dc3545;
  color: white;
  border: none;
  padding: 12px 24px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 1rem;
  font-weight: 500;
  width: 100%;
}

.mobile-logout-btn:hover {
  background-color: #c82333;
}

/* Main Content */
.main-content {
  flex: 1;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  padding: 20px;
}

/* Auth Container */
.auth-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - 104px);
  padding: 20px;
  position: relative;
}

.auth-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  padding: 40px;
  width: 100%;
  max-width: 400px;
}

.version-fixed {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  z-index: 10;
}

/* Tabs */
.tabs {
  display: flex;
  margin-bottom: 30px;
  border-bottom: 1px solid #e9ecef;
}

.tab {
  flex: 1;
  padding: 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  font-size: 1rem;
  color: #6c757d;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.tab.active {
  color: #007bff;
  border-bottom-color: #007bff;
  font-weight: 500;
}

.tab:hover {
  color: #007bff;
}

/* Form Styles */
.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #212529;
}

.form-group input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid #ced4da;
  border-radius: 6px;
  font-size: 1rem;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.form-group input:focus {
  outline: none;
  border-color: #007bff;
  box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
}

.auth-button {
  width: 100%;
  padding: 12px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 6px;
  font-size: 1rem;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 0.2s;
}

.auth-button:hover:not(:disabled) {
  background: #0056b3;
}

.auth-button:disabled {
  background: #6c757d;
  cursor: not-allowed;
}

/* Message Styles */
.error {
  background: #f8d7da;
  color: #721c24;
  padding: 12px 16px;
  border-radius: 6px;
  margin-top: 20px;
  border: 1px solid #f5c6cb;
}

.success {
  background: #d4edda;
  color: #155724;
  padding: 12px 16px;
  border-radius: 6px;
  margin-top: 20px;
  border: 1px solid #c3e6cb;
}

/* Mobile-first: Full width on very small screens */
@media (max-width: 480px) {
  .main-content {
    padding: 0;
  }
}

/* Responsive Breakpoints */
@media (min-width: 768px) {
  .desktop-nav {
    display: flex;
  }
  
  .mobile-menu-toggle {
    display: none;
  }
  
  .mobile-menu {
    display: none;
  }
  
  .main-content {
    padding: 40px 20px;
  }
  
  .auth-card {
    padding: 60px;
  }
}

@media (min-width: 1024px) {
  .header-content {
    padding: 0 40px;
  }
  
  .main-content {
    padding: 60px 40px;
  }
}
</style>