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

  // Actions
  setSessionId: (id: string) => void;
  addMessage: (msg: Omit<Message, 'id' | 'timestamp'>) => void;
  clearMessages: () => void;
  setLoading: (loading: boolean) => void;
  setThinking: (thinking: boolean) => void;
}

export const useChatStore = create<ChatState>(set => ({
  sessionId: null,
  messages: [],
  voiceAvailable: isVoiceSupported(),
  isLoading: false,
  isThinking: false,

  setSessionId: id => set({ sessionId: id }),

  addMessage: msg =>
    set(state => ({
      messages: [
        ...state.messages,
        {
          ...msg,
          id: crypto.randomUUID(),
          timestamp: Date.now(),
        },
      ],
    })),

  clearMessages: () => set({ messages: [] }),

  setLoading: loading => set({ isLoading: loading }),

  setThinking: thinking => set({ isThinking: thinking }),
}));
