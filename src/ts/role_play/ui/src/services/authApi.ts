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
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    username: string;
    email: string;
    role: string;
  };
}

export interface UserResponse {
  user: {
    id: string;
    username: string;
    email: string;
    role: string;
    created_at: string;
    updated_at: string;
  };
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

  async getCurrentUser(token: string): Promise<UserResponse> {
    const response = await axios.get<UserResponse>(
      apiUrl('/auth/me'),
      {
        headers: {
          Authorization: `Bearer ${token}`
        }
      }
    );
    return response.data;
  }
};