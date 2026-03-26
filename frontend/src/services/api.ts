// API service layer — Axios base client

import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

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

  /**
   * Stream chat response chunks for low-latency updates.
   * Yields text chunks as they arrive from the server.
   */
  async *streamMessage(
    req: ChatRequest,
    signal?: AbortSignal
  ): AsyncGenerator<string, void, unknown> {
    console.log('[streamMessage] Starting stream for message:', req.message.substring(0, 50));
    const token = localStorage.getItem('token');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }

    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers,
      body: JSON.stringify(req),
      signal,
    });

    console.log('[streamMessage] Response status:', response.status, 'ok:', response.ok);

    if (!response.ok) {
      const errorText = await response.text();
      console.error(
        '[streamMessage] Stream request failed:',
        response.status,
        response.statusText,
        errorText
      );
      throw new Error(
        `Stream request failed: ${response.status} ${response.statusText} - ${errorText}`
      );
    }

    const reader = response.body?.getReader();
    if (!reader) {
      console.error('[streamMessage] No response body');
      throw new Error('No response body');
    }

    const decoder = new TextDecoder();
    let buffer = '';
    let chunkCount = 0;

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        console.log('[streamMessage] Stream complete. Total chunks:', chunkCount);
        break;
      }

      const chunk = decoder.decode(value, { stream: true });
      buffer += chunk;
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            console.log('[streamMessage] SSE data:', JSON.stringify(data).substring(0, 200));
            if (data.chunk) {
              chunkCount++;
              console.log(
                '[streamMessage] Yielding chunk',
                chunkCount,
                ':',
                data.chunk.substring(0, 100)
              );
              yield data.chunk;
            } else if (data.thought) {
              // Agent is thinking — pass through with special prefix for UI display
              yield `__THOUGHT__:${data.thought}`;
            } else if (data.tool_call) {
              // Tool call started — pass through for UI display
              yield `__TOOL_CALL__:${data.tool_call}`;
            } else if (data.tool_result) {
              // Tool result received — pass through for UI display
              yield `__TOOL_RESULT__:${data.tool_result}`;
            } else if (data.status) {
              // Status update (e.g. retrying) — pass through
              yield `__STATUS__:${data.status}`;
            } else if (data.error) {
              console.error('[streamMessage] Stream error:', data.error);
              // data.error may be a string or an object like {code, message, status}
              const errorMsg =
                typeof data.error === 'string'
                  ? data.error
                  : data.error?.message || JSON.stringify(data.error);
              // Yield error as special marker instead of throwing
              // because async generators don't propagate thrown exceptions to for-await
              yield `__ERROR__:${errorMsg}`;
            } else if (data.done) {
              console.log('[streamMessage] Stream done signal received');
              return;
            }
          } catch (e) {
            if (e instanceof Error && e.message !== 'Skip malformed JSON') {
              console.error('[streamMessage] JSON parse error:', e);
            }
            // Skip malformed JSON
          }
        }
      }
    }
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
