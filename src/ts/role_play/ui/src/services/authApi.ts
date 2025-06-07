import axios from 'axios';
import { apiUrl } from './apiConfig';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  preferred_language?: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    username: string;
    email: string;
    role: string;
    preferred_language: string;
  };
}

export interface User {
  id: string;
  username: string;
  email: string;
  role: string;
  preferred_language: string;
  created_at: string;
  updated_at: string;
}

export interface UpdateLanguageRequest {
  language: string;
}

export interface UpdateLanguageResponse {
  success: boolean;
  language: string;
  message: string;
}

export const authApi = {
  async login(request: LoginRequest): Promise<AuthResponse> {
    const response = await axios.post<AuthResponse>(
      apiUrl('/auth/login'),
      request
    );
    return response.data;
  },

  async register(request: RegisterRequest): Promise<AuthResponse> {
    const response = await axios.post<AuthResponse>(
      apiUrl('/auth/register'),
      request
    );
    return response.data;
  },

  async getCurrentUser(token: string): Promise<User> {
    const response = await axios.get<User>(
      apiUrl('/auth/me'),
      {
        headers: {
          Authorization: `Bearer ${token}`
        }
      }
    );
    return response.data;
  },

  async updateLanguagePreference(token: string, request: UpdateLanguageRequest): Promise<UpdateLanguageResponse> {
    const response = await axios.patch<UpdateLanguageResponse>(
      apiUrl('/auth/language'),
      request,
      {
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      }
    );
    return response.data;
  }
};