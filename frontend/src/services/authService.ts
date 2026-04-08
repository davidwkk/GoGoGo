// Authentication service — wraps /auth/* API calls

import { apiClient } from '@/services/api';
import { AuthResponse } from '@/types/auth';

/**
 * Authentication service wrapping /auth/* endpoints.
 */
export const authService = {
  /**
   * Sign in with email + password.
   * Returns the raw AuthResponse (caller stores via useAuthStore.setAuth).
   */
  async login(email: string, password: string): Promise<AuthResponse> {
    const { data } = await apiClient.post<AuthResponse>('/auth/login', { email, password });
    return data;
  },

  /**
   * Create a new account.
   * Returns the raw AuthResponse (caller stores via useAuthStore.setAuth).
   */
  async register(email: string, username: string, password: string): Promise<AuthResponse> {
    const { data } = await apiClient.post<AuthResponse>('/auth/register', {
      email,
      username,
      password,
    });
    return data;
  },
};
