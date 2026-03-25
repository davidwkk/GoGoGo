// useTTS - Text-to-speech using browser's native window.speechSynthesis API
// Phase 1: Browser TTS (no API key required)
// Future: swap to Gemini TTS API if browser TTS quality is insufficient

import { useCallback, useState } from "react";

export function isTTSAvailable(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

interface UseTTSOptions {
  onStart?: () => void;
  onEnd?: () => void;
  onError?: (error: string) => void;
}

export function useTTS({ onStart, onEnd, onError }: UseTTSOptions = {}) {
  const [isSpeaking, setIsSpeaking] = useState(false);

  const speak = useCallback(
    (text: string, lang = "en-US") => {
      if (!isTTSAvailable()) {
        onError?.("TTS not available in this browser");
        return;
      }

      // Cancel any ongoing speech
      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      utterance.lang = lang;
      utterance.rate = 1.0;
      utterance.pitch = 1.0;

      utterance.onstart = () => {
        setIsSpeaking(true);
        onStart?.();
      };

      utterance.onend = () => {
        setIsSpeaking(false);
        onEnd?.();
      };

      utterance.onerror = (event) => {
        setIsSpeaking(false);
        onError?.(`TTS error: ${event.error}`);
      };

      window.speechSynthesis.speak(utterance);
    },
    [onStart, onEnd, onError]
  );

  const stop = useCallback(() => {
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

