import axios from 'axios'
import { API_BASE_URL } from './apiConfig'

interface UpdateLanguageRequest {
  language: string
}

interface UpdateLanguageResponse {
  success: boolean
  message?: string
}

class UserApi {
  private getAuthHeaders() {
    const token = localStorage.getItem('token')
    return {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    }
  }

  async updateLanguagePreference(language: string): Promise<UpdateLanguageResponse> {
    try {
      const response = await axios.patch(
        `${API_BASE_URL}/user/language`,
        { language } as UpdateLanguageRequest,
        { headers: this.getAuthHeaders() }
      )
      
      return response.data
    } catch (error) {
      console.error('Failed to update language preference:', error)
      throw error
    }
  }

  async getUserProfile() {
    try {
      const response = await axios.get(
        `${API_BASE_URL}/user/profile`,
        { headers: this.getAuthHeaders() }
      )
      
      return response.data
    } catch (error) {
      console.error('Failed to get user profile:', error)
      throw error
    }
  }
}

export const userApi = new UserApi()
