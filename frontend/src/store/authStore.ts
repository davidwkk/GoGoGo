// Zustand store for authentication state

import { create } from 'zustand';
import { AuthUser } from '@/types/auth';

interface AuthState {
  // ─── State ───────────────────────────────────────────────
  user: AuthUser | null;
  token: string | null;

  // ─── Actions ─────────────────────────────────────────────
  setAuth: (user: AuthUser, token: string) => void;
  clearAuth: () => void;
  initAuth: () => void;
}

// ─── localStorage helpers ─────────────────────────────────────────────────

const getStoredToken = (): string | null => localStorage.getItem('access_token');

const getStoredUser = (): AuthUser | null => {
  const email = localStorage.getItem('user_email');
  if (!email) return null;
  return { email, username: '' };
};

// ─── Store ────────────────────────────────────────────────────────────────

export const useAuthStore = create<AuthState>(set => ({
  user: null,
  token: null,

  setAuth: (user, token) => {
    localStorage.setItem('access_token', token);
    localStorage.setItem('user_email', user.email);
    set({ user, token });
  },

  clearAuth: () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('user_email');
    // Note: rememberMe is intentionally NOT cleared so the email field
    // can still be pre-filled on the next login screen.
    set({ user: null, token: null });
  },

  initAuth: () => {
    const token = getStoredToken();
    const user = getStoredUser();
    if (token && user) {
      set({ token, user });
    }
  },
}));

// ─── Selectors ────────────────────────────────────────────────────────────

export const selectIsAuthenticated = (state: AuthState) => !!state.token;
export const selectCurrentUser = (state: AuthState) => state.user;
export const selectToken = (state: AuthState) => state.token;
