<template>
  <div class="container">
    <h1>Role Play System</h1>
    
    <!-- Logged in view -->
    <div v-if="user" class="user-info">
      <h2>Welcome, {{ user.username }}!</h2>
      <p><strong>Email:</strong> {{ user.email }}</p>
      <p><strong>Role:</strong> {{ user.role }}</p>
      <p><strong>User ID:</strong> {{ user.id }}</p>
      <button @click="logout" class="logout-btn">Logout</button>
    </div>
    
    <!-- Login/Register view -->
    <div v-else>
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
        <button type="submit" :disabled="loading">
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
        <button type="submit" :disabled="loading">
          {{ loading ? 'Registering...' : 'Register' }}
        </button>
      </form>

      <!-- Error/Success Messages -->
      <div v-if="error" class="error">{{ error }}</div>
      <div v-if="success" class="success">{{ success }}</div>
    </div>
  </div>
</template>

<script>
import axios from 'axios'

export default {
  name: 'App',
  data() {
    return {
      activeTab: 'login',
      loading: false,
      error: '',
      success: '',
      user: null,
      token: localStorage.getItem('auth_token'),
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
        localStorage.setItem('auth_token', this.token)
        
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
        localStorage.setItem('auth_token', this.token)
        
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
      localStorage.removeItem('auth_token')
      this.success = 'Logged out successfully'
      this.error = ''
    }
  }
}
</script>

<style>
.logout-btn {
  background-color: #dc3545;
}
.logout-btn:hover {
  background-color: #c82333;
}
</style>