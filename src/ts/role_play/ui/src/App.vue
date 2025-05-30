<template>
  <div class="app">
    <!-- Navigation Header -->
    <header class="app-header">
      <div class="header-content">
        <h1 class="app-title">Role Play System</h1>
        
        <!-- Desktop Navigation -->
        <nav v-if="user" class="desktop-nav">
          <div class="user-info">
            <span class="user-name">{{ user.username }}</span>
            <span class="user-role">{{ user.role }}</span>
          </div>
          <div class="nav-actions">
            <button @click="logout" class="logout-btn">Logout</button>
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
        <div class="mobile-user-info">
          <div class="user-details">
            <strong>{{ user.username }}</strong>
            <p>{{ user.email }}</p>
            <span class="role-badge">{{ user.role }}</span>
          </div>
        </div>
        <div class="mobile-actions">
          <button @click="logout" class="mobile-logout-btn">Logout</button>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="main-content">
      <!-- Logged in view -->
      <div v-if="user">
        <!-- Chat Component -->
        <Chat />
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
              Login
            </button>
            <button 
              class="tab" 
              :class="{ active: activeTab === 'register' }"
              @click="activeTab = 'register'"
            >
              Register
            </button>
          </div>

          <!-- Login Form -->
          <form v-if="activeTab === 'login'" @submit.prevent="login">
            <div class="form-group">
              <label for="login-email">Email:</label>
              <input 
                id="login-email"
                v-model="loginForm.email" 
                type="email" 
                required 
                :disabled="loading"
              />
            </div>
            <div class="form-group">
              <label for="login-password">Password:</label>
              <input 
                id="login-password"
                v-model="loginForm.password" 
                type="password" 
                required 
                :disabled="loading"
              />
            </div>
            <button type="submit" :disabled="loading" class="auth-button">
              {{ loading ? 'Logging in...' : 'Login' }}
            </button>
          </form>

          <!-- Register Form -->
          <form v-if="activeTab === 'register'" @submit.prevent="register">
            <div class="form-group">
              <label for="register-username">Username:</label>
              <input 
                id="register-username"
                v-model="registerForm.username" 
                type="text" 
                required 
                :disabled="loading"
              />
            </div>
            <div class="form-group">
              <label for="register-email">Email:</label>
              <input 
                id="register-email"
                v-model="registerForm.email" 
                type="email" 
                required 
                :disabled="loading"
              />
            </div>
            <div class="form-group">
              <label for="register-password">Password:</label>
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
              {{ loading ? 'Registering...' : 'Register' }}
            </button>
          </form>

          <!-- Error/Success Messages -->
          <div v-if="error" class="error">{{ error }}</div>
          <div v-if="success" class="success">{{ success }}</div>
        </div>
      </div>
    </main>
  </div>
</template>

<script>
import axios from 'axios'
import Chat from './components/Chat.vue'

export default {
  name: 'App',
  components: {
    Chat
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
        const response = await axios.post('http://localhost:8000/auth/login', {
          email: this.loginForm.email,
          password: this.loginForm.password
        })
        
        this.token = response.data.access_token
        this.user = response.data.user
        localStorage.setItem('token', this.token)
        
        this.success = 'Login successful!'
        this.loginForm = { email: '', password: '' }
        
      } catch (error) {
        this.error = error.response?.data?.detail || 'Login failed'
      } finally {
        this.loading = false
      }
    },
    
    async register() {
      this.loading = true
      this.error = ''
      this.success = ''
      
      try {
        const response = await axios.post('http://localhost:8000/auth/register', {
          username: this.registerForm.username,
          email: this.registerForm.email,
          password: this.registerForm.password
        })
        
        this.token = response.data.access_token
        this.user = response.data.user
        localStorage.setItem('token', this.token)
        
        this.success = 'Registration successful!'
        this.registerForm = { username: '', email: '', password: '' }
        
      } catch (error) {
        this.error = error.response?.data?.detail || 'Registration failed'
      } finally {
        this.loading = false
      }
    },
    
    async getCurrentUser() {
      try {
        const response = await axios.get('http://localhost:8000/auth/me', {
          headers: {
            'Authorization': `Bearer ${this.token}`
          }
        })
        this.user = response.data.user
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
      this.success = 'Logged out successfully'
      this.error = ''
    },
    
    toggleMobileMenu() {
      this.showMobileMenu = !this.showMobileMenu
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
  justify-content: center;
  align-items: center;
  min-height: calc(100vh - 104px);
  padding: 20px;
}

.auth-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  padding: 40px;
  width: 100%;
  max-width: 400px;
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