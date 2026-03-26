// API service layer — Axios base client

import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

// Attach JWT token if present
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
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
  message_type: "chat" | "itinerary" | "error";
  history?: Array<{ role: string; content: string; created_at: string }>;
}

export const chatService = {
  async sendMessage(req: ChatRequest): Promise<ChatResponse> {
    const { data } = await apiClient.post<ChatResponse>("/chat", req);
    return data;
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
  id: number;
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
    const { data } = await apiClient.get<UserProfile>("/users/me");
    return data;
  },

  async updateProfile(req: UpdateProfileRequest): Promise<UserProfile> {
    const { data } = await apiClient.patch<UserProfile>("/users/me", req);
    return data;
  },
};

