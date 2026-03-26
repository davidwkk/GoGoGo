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

  // Agent thinking steps (tool calls, status updates during streaming)
  thinkingSteps: string[];

  // Actions
  setSessionId: (id: string | null) => void;
  addMessage: (msg: Omit<Message, 'id' | 'timestamp'>) => string;
  updateStreamingMessage: (id: string, content: string) => void;
  clearMessages: () => void;
  setLoading: (loading: boolean) => void;
  setThinking: (thinking: boolean) => void;
  setAbortController: (controller: AbortController | null) => void;
  addThinkingStep: (step: string) => void;
  clearThinkingSteps: () => void;
}

export const useChatStore = create<ChatState>(set => ({
  sessionId: null,
  messages: [],
  voiceAvailable: isVoiceSupported(),
  isLoading: false,
  isThinking: false,
  abortController: null,
  thinkingSteps: [],

  setSessionId: id => set({ sessionId: id }),

  addMessage: msg => {
    const id = crypto.randomUUID();
    set(state => ({
      messages: [...state.messages, { ...msg, id, timestamp: Date.now() }],
    }));
    return id;
  },

  updateStreamingMessage: (id, content) =>
    set(state => ({
      messages: state.messages.map(msg => (msg.id === id ? { ...msg, content } : msg)),
    })),

  clearMessages: () => set({ messages: [] }),

  setLoading: loading => set({ isLoading: loading }),

  setThinking: thinking => set({ isThinking: thinking }),

  setAbortController: controller => set({ abortController: controller }),

  addThinkingStep: step =>
    set(state => ({
      thinkingSteps: [...state.thinkingSteps, step],
    })),

  clearThinkingSteps: () => set({ thinkingSteps: [] }),
}));
