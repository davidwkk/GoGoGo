// API service layer — Axios base client

import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
});

// Attach JWT token if present
apiClient.interceptors.request.use(config => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export interface ChatRequest {
  message: string;
  session_id?: string;
  generate_plan: boolean;
  trip_parameters?: {
    destination: string;
    start_date: string;
    end_date: string;
    group_type: string;
    group_size: number;
    purpose: string;
    is_round_trip: boolean;
  };
  user_preferences?: Record<string, unknown>;
}

export interface ChatResponse {
  session_id: string;
  text: string;
  itinerary: unknown | null;
  message_type: 'chat' | 'itinerary' | 'error';
  history?: Array<{ role: string; content: string; created_at: string }>;
}

export const chatService = {
  async sendMessage(req: ChatRequest): Promise<ChatResponse> {
    const { data } = await apiClient.post<ChatResponse>('/chat', req);
    return data;
  },
};

// ─── Guest Preferences (localStorage) ─────────────────────────────────────────

export interface GuestPreferences {
  travel_style: string;
  dietary_restriction: string;
  hotel_tier: string;
  budget_min_hkd: number;
  budget_max_hkd: number;
  max_flight_stops: number;
}

const GUEST_PREFS_KEY = 'guest_preferences';

export const DEFAULT_GUEST_PREFERENCES: GuestPreferences = {
  travel_style: 'relaxing',
  dietary_restriction: 'none',
  hotel_tier: 'mid_range',
  budget_min_hkd: 5000,
  budget_max_hkd: 20000,
  max_flight_stops: 1,
};

export const guestPreferences = {
  get(): GuestPreferences {
    try {
      const stored = localStorage.getItem(GUEST_PREFS_KEY);
      return stored ? JSON.parse(stored) : DEFAULT_GUEST_PREFERENCES;
    } catch {
      return DEFAULT_GUEST_PREFERENCES;
    }
  },

  set(prefs: GuestPreferences): void {
    localStorage.setItem(GUEST_PREFS_KEY, JSON.stringify(prefs));
  },
};

// ─── User / Profile ───────────────────────────────────────────────────────────

export interface UserPreferences {
  travel_style: string;
  dietary_restriction: string;
  hotel_tier: string;
  budget_min_hkd: number;
  budget_max_hkd: number;
  max_flight_stops: number;
}

export interface UserProfile {
  id: string;
  username: string;
  email: string;
  preferences: UserPreferences | null;
  created_at: string;
}

export interface UpdateProfileRequest {
  username?: string;
  preferences?: Partial<UserPreferences>;
}

export const userService = {
  async getProfile(): Promise<UserProfile> {
    const { data } = await apiClient.get<UserProfile>('/users/me');
    return data;
  },

  async updateProfile(req: UpdateProfileRequest): Promise<UserProfile> {
    const { data } = await apiClient.patch<UserProfile>('/users/me', req);
    return data;
  },
};
