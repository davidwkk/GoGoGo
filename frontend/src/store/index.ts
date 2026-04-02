// Zustand store for app state

import { isVoiceSupported } from '@/hooks/useASR';
import { create } from 'zustand';
import { DEFAULT_TRAVEL_SETTINGS, TravelSettings } from '@/types/trip';

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  messageType?: string;
  thinking_steps?: string[];
}

export interface ChatState {
  // Session
  sessionId: string | null;
  messages: Message[];
  forceNewSessionNextMessage: boolean;

  // Voice
  voiceAvailable: boolean;

  // UI state
  isLoading: boolean;
  isThinking: boolean;

  // Stream cancellation
  abortController: AbortController | null;

  // Agent thinking steps (tool calls, status updates during streaming)
  thinkingSteps: string[];

  // Partial thought text being currently streamed (for typewriter effect)
  partialThoughtText: string;

  // Travel Settings
  travelSettings: TravelSettings;

  // Actions
  setSessionId: (id: string | null) => void;
  setMessages: (messages: Message[]) => void;
  setForceNewSessionNextMessage: (force: boolean) => void;
  addMessage: (msg: Omit<Message, 'id' | 'timestamp'>) => string;
  updateStreamingMessage: (
    id: string,
    content: string,
    messageType?: string,
    thinking_steps?: string[]
  ) => void;
  clearMessages: () => void;
  setLoading: (loading: boolean) => void;
  setThinking: (thinking: boolean) => void;
  setAbortController: (controller: AbortController | null) => void;
  addThinkingStep: (step: string) => void;
  setPartialThoughtText: (text: string) => void;
  setTravelSettings: (settings: Partial<TravelSettings>) => void;
  resetTravelSettings: () => void;
}

export const useChatStore = create<ChatState>(set => ({
  sessionId: null,
  messages: [],
  forceNewSessionNextMessage: false,
  voiceAvailable: isVoiceSupported(),
  isLoading: false,
  isThinking: false,
  abortController: null,
  thinkingSteps: [],
  partialThoughtText: '',

  travelSettings: DEFAULT_TRAVEL_SETTINGS,

  setSessionId: id => set({ sessionId: id }),
  setMessages: messages => set({ messages }),
  setForceNewSessionNextMessage: force => set({ forceNewSessionNextMessage: force }),

  addMessage: msg => {
    const id = crypto.randomUUID();
    set(state => ({
      messages: [...state.messages, { ...msg, id, timestamp: Date.now() }],
    }));
    return id;
  },

  updateStreamingMessage: (id, content, messageType, thinking_steps) =>
    set(state => ({
      messages: state.messages.map(msg =>
        msg.id === id
          ? {
              ...msg,
              content,
              ...(messageType !== undefined ? { messageType } : {}),
              ...(thinking_steps !== undefined ? { thinking_steps } : {}),
            }
          : msg
      ),
    })),

  clearMessages: () => set({ messages: [] }),

  setLoading: loading => set({ isLoading: loading }),

  setThinking: thinking => set({ isThinking: thinking }),

  setAbortController: controller => set({ abortController: controller }),

  addThinkingStep: step =>
    set(state => ({
      thinkingSteps: [...state.thinkingSteps, step],
    })),

  setPartialThoughtText: text => set({ partialThoughtText: text }),

  setTravelSettings: settings =>
    set(state => ({
      travelSettings: { ...state.travelSettings, ...settings },
    })),

  resetTravelSettings: () => set({ travelSettings: DEFAULT_TRAVEL_SETTINGS }),
}));
