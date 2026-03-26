// Zustand store for app state

import { create } from 'zustand';
import { isVoiceSupported } from '@/hooks/useASR';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
}

export interface ChatState {
  // Session
  sessionId: string | null;
  messages: Message[];

  // Voice
  voiceAvailable: boolean;

  // UI state
  isLoading: boolean;
  isThinking: boolean;

  // Stream cancellation
  abortController: AbortController | null;

  // Actions
  setSessionId: (id: string) => void;
  addMessage: (msg: Omit<Message, 'id' | 'timestamp'>) => string;
  updateStreamingMessage: (id: string, content: string) => void;
  clearMessages: () => void;
  setLoading: (loading: boolean) => void;
  setThinking: (thinking: boolean) => void;
  setAbortController: (controller: AbortController | null) => void;
}

export const useChatStore = create<ChatState>(set => ({
  sessionId: null,
  messages: [],
  voiceAvailable: isVoiceSupported(),
  isLoading: false,
  isThinking: false,
  abortController: null,

  setSessionId: id => set({ sessionId: id }),

  addMessage: msg =>
    set(state => {
      const newMsg = {
        ...msg,
        id: crypto.randomUUID(),
        timestamp: Date.now(),
      };
      return { messages: [...state.messages, newMsg] };
    }),

  updateStreamingMessage: (id, content) =>
    set(state => ({
      messages: state.messages.map(msg => (msg.id === id ? { ...msg, content } : msg)),
    })),

  clearMessages: () => set({ messages: [] }),

  setLoading: loading => set({ isLoading: loading }),

  setThinking: thinking => set({ isThinking: thinking }),

  setAbortController: controller => set({ abortController: controller }),
}));
