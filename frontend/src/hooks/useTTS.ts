// useTTS - Text-to-speech using browser's native window.speechSynthesis API
// Phase 1: Browser TTS (no API key required)
// Future: swap to Gemini TTS API if browser TTS quality is insufficient

import { useCallback, useRef, useState } from 'react';

export function isTTSAvailable(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window;
}

interface UseTTSOptions {
  onStart?: () => void;
  onEnd?: () => void;
  onError?: (error: string) => void;
}

export function useTTS({ onStart, onEnd, onError }: UseTTSOptions = {}) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const utteranceIdRef = useRef(0);

  const speak = useCallback(
    (text: string, lang = 'en-US') => {
      if (!isTTSAvailable()) {
        onError?.('TTS not available in this browser');
        return;
      }

      const utteranceId = ++utteranceIdRef.current;
      // Cancel any ongoing speech
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = lang;
      utterance.rate = 1.0;
      utterance.pitch = 1.0;

      utterance.onstart = () => {
        // Ignore callbacks from a cancelled/old utterance
        if (utteranceId !== utteranceIdRef.current) return;
        setIsSpeaking(true);
        onStart?.();
      };

      utterance.onend = () => {
        if (utteranceId !== utteranceIdRef.current) return;
        setIsSpeaking(false);
        onEnd?.();
      };

      utterance.onerror = event => {
        if (utteranceId !== utteranceIdRef.current) return;
        setIsSpeaking(false);
        onError?.(`TTS error: ${event.error}`);
      };

      window.speechSynthesis.speak(utterance);
    },
    [onStart, onEnd, onError]
  );

  const stop = useCallback(() => {
    utteranceIdRef.current++;
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }, []);

  return {
    isSpeaking,
    speak,
    stop,
    isAvailable: isTTSAvailable(),
  };
}
