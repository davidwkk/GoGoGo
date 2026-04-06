// frontend/src/services/api.ts

import axios from 'axios';

const DEBUG = import.meta.env.DEV;
const log = (...args: unknown[]) => {
  if (DEBUG) console.log(...args);
};
const warn = (...args: unknown[]) => {
  if (DEBUG) console.warn(...args);
};
const error = (...args: unknown[]) => {
  if (DEBUG) console.error(...args);
};

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

// 1. Define the Standardized Error Envelope
export interface APIError {
  detail: string;
  code?: string;
  statusCode?: number;
  isNetworkError?: boolean;
}

export const apiClient = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
  timeout: 60000, // 60-second global timeout for all requests
});

// Attach JWT token if present
apiClient.interceptors.request.use(config => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Helper to strip HTML tags and prevent XSS in error messages
const sanitizeHTML = (str: string): string => {
  if (typeof str !== 'string') return 'Unknown error';
  // Removes anything inside < > brackets
  return str.replace(/<\/?[^>]+(>|$)/g, '');
};

// THE BOUNCER: Handle all errors and format them into APIError
apiClient.interceptors.response.use(
  response => response,
  error => {
    // Start with a default error shape
    const apiError: APIError = {
      detail: 'An unexpected error occurred. Please try again.',
      statusCode: error.response?.status,
    };

    // Handle Network & Timeout Errors
    if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
      apiError.detail = 'The request took too long. Please check your connection and try again.';
      apiError.code = 'TIMEOUT';
      apiError.isNetworkError = true;
    } else if (!error.response) {
      apiError.detail = 'Network error. Are you connected to the internet?';
      apiError.code = 'NETWORK_ERROR';
      apiError.isNetworkError = true;
    }
    // Handle Server Errors (FastAPI formatting)
    // Handle Server Errors (FastAPI formatting)
    else {
      const data = error.response.data;
      if (data && data.detail) {
        // FastAPI validation errors return an array of issues
        if (Array.isArray(data.detail)) {
          apiError.detail = data.detail
            .map((err: any) => {
              const field = err.loc?.[err.loc.length - 1];
              // Sanitize the specific error message
              const safeMsg = sanitizeHTML(err.msg);
              return field ? `${field}: ${safeMsg}` : safeMsg;
            })
            .join(', ');
        } else {
          // Standard string detail (e.g., "Invalid credentials")
          apiError.detail = sanitizeHTML(data.detail); // Sanitize the main string
        }
      } else if (error.response.status >= 500) {
        apiError.detail = 'Our servers are currently experiencing issues. Please try again later.';
      }
    }

    // Auth graceful fallback
    const status = error.response?.status;
    const endpoint = error.config?.url;
    if (endpoint?.includes('/users/me') || endpoint?.includes('/trips')) {
      if (status === 401 || status === 404) {
        localStorage.removeItem('access_token');
        window.location.href = '/login';
        apiError.detail =
          status === 401
            ? 'Your session has expired. Please login again.'
            : 'Your account could not be found. Please login again.';
      }
    }

    // Always reject with the clean APIError object
    return Promise.reject(apiError);
  }
);

export interface ChatRequest {
  message: string;
  session_id?: string;
  force_new_session?: boolean;
  generate_plan: boolean;
  trip_parameters?: {
    destination: string;
    start_date: string;
    end_date: string;
    group_type: string;
    group_size: number;
    purpose: string;
  };
  user_preferences?: Record<string, unknown>;
}

export interface ChatResponse {
  session_id: string;
  text: string;
  itinerary: unknown | null;
  message_type: 'chat' | 'itinerary' | 'error' | 'tool_result';
  history?: Array<{ role: string; content: string; created_at: string }>;
}

export interface ChatSessionMessagesResponse {
  session_id: string | null;
  messages: Array<{
    id: number;
    role: string;
    content: string;
    message_type?: string;
    thinking_steps?: string[];
    created_at: string | null;
  }>;
}

export const chatService = {
  async sendMessage(req: ChatRequest): Promise<ChatResponse> {
    const { data } = await apiClient.post<ChatResponse>('/chat', req, {
      // Keep the 180s override here because the AI can definitely
      // take longer than a minute to plan a full 7-day trip!
      timeout: 180000,
    });
    return data;
  },

  /**
   * Stream chat response chunks for low-latency updates.
   * Yields text chunks as they arrive from the server.
   * Retries up to 3 times with exponential backoff on SSE disconnect.
   */
  async *streamMessage(
    req: ChatRequest,
    signal?: AbortSignal
  ): AsyncGenerator<string, void, unknown> {
    const MAX_RETRIES = 4; // 1 initial + up to 3 retries
    const BASE_DELAY_MS = 500;
    let attempt = 0;

    let exhaustedError: string | null = null;

    while (attempt <= MAX_RETRIES) {
      attempt++;
      if (signal?.aborted) {
        log('[streamMessage] Aborted by caller, stopping');
        return;
      }
      if (attempt > 1) {
        const delay = BASE_DELAY_MS * Math.pow(2, attempt - 2);
        log(`[streamMessage] Retry ${attempt - 1}/${MAX_RETRIES - 1} after ${delay}ms backoff`);
        await new Promise(resolve => setTimeout(resolve, delay));
        // Check again after backoff — user may have started a new chat
        if (signal?.aborted) {
          log('[streamMessage] Aborted after backoff, stopping retries');
          return;
        }
      }

      let response: Response;
      try {
        log('[streamMessage] Starting stream for message:', req.message.substring(0, 50));
        const token = localStorage.getItem('access_token');
        const headers: Record<string, string> = { 'Content-Type': 'application/json' };
        if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }

        response = await fetch(`${API_BASE}/chat/stream`, {
          method: 'POST',
          headers,
          body: JSON.stringify(req),
          signal,
        });
      } catch (fetchErr) {
        warn('[streamMessage] Fetch error, retrying:', fetchErr);
        if (attempt >= MAX_RETRIES)
          exhaustedError = 'Connection failed. Please check your network and try again.';
        continue;
      }

      log('[streamMessage] Response status:', response.status, 'ok:', response.ok);

      if (!response.ok) {
        const errorText = await response.text();
        error(
          '[streamMessage] Stream request failed:',
          response.status,
          response.statusText,
          errorText
        );
        if (attempt >= MAX_RETRIES)
          exhaustedError = `Server error (${response.status}). Please try again later.`;
        continue;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        error('[streamMessage] No response body');
        if (attempt >= MAX_RETRIES) exhaustedError = 'No response from server. Please try again.';
        continue;
      }

      const decoder = new TextDecoder();
      let buffer = '';
      let chunkCount = 0;

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            log('[streamMessage] Stream complete. Total chunks:', chunkCount);
            return;
          }

          const chunk = decoder.decode(value, { stream: true });
          buffer += chunk;
          const lines = buffer.split('\n');
          buffer = lines.pop() ?? '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6));
                log('[streamMessage] SSE data:', JSON.stringify(data).substring(0, 200));
                if (data.chunk) {
                  chunkCount++;
                  log(
                    '[streamMessage] Yielding chunk',
                    chunkCount,
                    ':',
                    data.chunk.substring(0, 100)
                  );
                  yield data.chunk;
                } else if (data.thought) {
                  yield `__THOUGHT__:${data.thought}`;
                } else if (data.model_thought) {
                  yield `__MODEL_THOUGHT__:${data.model_thought}`;
                } else if (data.tool_call) {
                  yield `__TOOL_CALL__:${data.tool_call}`;
                } else if (data.tool_result) {
                  yield `__TOOL_RESULT__:${data.tool_result}`;
                } else if (data.status) {
                  yield `__STATUS__:${data.status}`;
                } else if (data.error) {
                  error('[streamMessage] Stream error:', data.error);
                  const errorMsg =
                    typeof data.error === 'string'
                      ? data.error
                      : data.error?.message || JSON.stringify(data.error);
                  yield `__ERROR__:${errorMsg}`;
                } else if (data.message_id !== undefined) {
                  yield `__MESSAGE_ID__:${data.message_id}`;
                } else if (data.done) {
                  log('[streamMessage] Stream done signal received');
                  return;
                }
              } catch (e) {
                if (e instanceof Error && e.message !== 'Skip malformed JSON') {
                  error('[streamMessage] JSON parse error:', e);
                }
              }
            }
          }
        }
      } catch (streamErr) {
        warn('[streamMessage] Stream broken, will retry:', streamErr);
        reader.cancel().catch(() => {});
        if (attempt >= MAX_RETRIES) exhaustedError = 'Connection lost. Please try again.';
        continue;
      }
    }

    if (exhaustedError) {
      error('[streamMessage] All retries exhausted');
      yield `__ERROR__:${exhaustedError}`;
    }
  },
};

export const chatSessionsService = {
  async getActive(guest_uid?: string): Promise<ChatSessionMessagesResponse> {
    const { data } = await apiClient.get<ChatSessionMessagesResponse>('/chat/sessions/active', {
      params: guest_uid ? { guest_uid } : undefined,
    });
    return data;
  },

  async list(): Promise<{
    sessions: Array<{ id: number; title: string; created_at: string | null }>;
  }> {
    const { data } = await apiClient.get('/chat/sessions');
    return data;
  },

  async create(): Promise<{ session_id: number; title: string; created_at: string | null }> {
    const { data } = await apiClient.post('/chat/sessions');
    return data;
  },

  async rename(
    sessionId: number,
    title: string
  ): Promise<{ id: number; title: string; created_at: string | null }> {
    const { data } = await apiClient.patch(`/chat/sessions/${sessionId}`, { title });
    return data;
  },

  async delete(sessionId: number): Promise<{ status: string; session_id: number }> {
    const { data } = await apiClient.delete(`/chat/sessions/${sessionId}`);
    return data;
  },

  async end(sessionId: number): Promise<{ status: string; session_id: number }> {
    const { data } = await apiClient.post(`/chat/sessions/${sessionId}/end`);
    return data;
  },

  async getMessages(sessionId: number): Promise<ChatSessionMessagesResponse> {
    const { data } = await apiClient.get<ChatSessionMessagesResponse>(
      `/chat/sessions/${sessionId}/messages`
    );
    return data;
  },

  async updateThinkingSteps(
    messageId: number,
    thinkingSteps: string[],
    guestUid?: string
  ): Promise<{ ok: boolean }> {
    const params = guestUid ? { guest_uid: guestUid } : undefined;
    const { data } = await apiClient.patch<{ ok: boolean }>(
      `/chat/messages/${messageId}/thinking-steps`,
      { thinking_steps: thinkingSteps },
      { params }
    );
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
