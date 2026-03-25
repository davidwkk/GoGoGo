// useASR - Voice input using Web Speech API (SpeechRecognition)
// Returns transcript via onTranscript callback
// MUST: mute useTTS when recording starts (handled by parent via isListening)
// MUST: handle permission denial gracefully → text fallback

import { useCallback, useRef, useState } from "react";

export interface ASRResult {
  transcript: string;
  isFinal: boolean;
}

export function isVoiceSupported(): boolean {
  return (
    typeof window !== "undefined" &&
    ("SpeechRecognition" in window || "webkitSpeechRecognition" in window)
  );
}

interface UseASROptions {
  onTranscript: (result: ASRResult) => void;
  onError?: (error: string) => void;
}

export function useASR({ onTranscript, onError }: UseASROptions) {
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<any>(null);

  const startListening = useCallback(() => {
    if (!isVoiceSupported()) {
      onError?.("Speech recognition not supported in this browser");
      return;
    }

    const SpeechRecognition =
      (window as any).SpeechRecognition ||
      (window as any).webkitSpeechRecognition;

    const recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = true;
    recognition.lang = "en-US";

    recognition.onstart = () => setIsListening(true);

    recognition.onresult = (event: any) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        onTranscript({
          transcript: result[0].transcript,
          isFinal: result.isFinal,
        });
      }
    };

    recognition.onerror = (event: any) => {
      setIsListening(false);
      if (event.error === "not-allowed") {
        onError?.("Microphone permission denied. Please use text input.");
      } else {
        onError?.(`Speech error: ${event.error}`);
      }
    };

    recognition.onend = () => setIsListening(false);

    recognitionRef.current = recognition;
    recognition.start();
  }, [onTranscript, onError]);

  const stopListening = useCallback(() => {
    recognitionRef.current?.stop();
    setIsListening(false);
  }, []);

  return {
    isListening,
    startListening,
    stopListening,
    isSupported: isVoiceSupported(),
  };
}

