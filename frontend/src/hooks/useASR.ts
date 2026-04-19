// useASR - Voice input using Web Speech API (SpeechRecognition)
// Session: up to 60s; auto-stops after 20s with no recognized speech; user can stop anytime.

import { useCallback, useEffect, useRef, useState } from 'react';

export interface ASRResult {
  transcript: string;
  isFinal: boolean;
}

export function isVoiceSupported(): boolean {
  return (
    typeof window !== 'undefined' &&
    ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)
  );
}

const SILENCE_MS = 20_000;
const MAX_SESSION_MS = 60_000;
const RESTART_DEBOUNCE_MS = 250;

interface UseASROptions {
  onTranscript: (result: ASRResult) => void;
  onError?: (error: string) => void;
}

interface Callbacks {
  onTranscript: (result: ASRResult) => void;
  onError?: (error: string) => void;
}

/** Minimal Web Speech API types (not in default TS `lib.dom` in this project). */
type SpeechRecognitionCtor = new () => SpeechRecognitionLike;
interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onresult: ((ev: SpeechRecognitionResultEvent) => void) | null;
  onerror: ((ev: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}
interface SpeechRecognitionResultEvent {
  results: {
    length: number;
    [index: number]: {
      readonly isFinal: boolean;
      [index: number]: { transcript: string };
    };
  };
}
interface SpeechRecognitionErrorEvent {
  error: string;
}

type WindowWithSpeech = Window & {
  SpeechRecognition?: SpeechRecognitionCtor;
  webkitSpeechRecognition?: SpeechRecognitionCtor;
};

export function useASR({ onTranscript, onError }: UseASROptions) {
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const callbacksRef = useRef<Callbacks>({ onTranscript, onError });
  callbacksRef.current = { onTranscript, onError };

  const startRecognitionRef = useRef<() => void>(() => {});

  /** User session still active — false only after max time, silence, manual stop, or fatal error. */
  const shouldContinueRef = useRef(false);
  const sessionStartedAtRef = useRef(0);
  /** Text finalized before the current recognition instance (after browser onend restarts). */
  const committedPrefixRef = useRef('');
  /** Latest full transcript for this recording session (for prefix when restarting). */
  const lastFullTranscriptRef = useRef('');
  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const maxTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearTimers = useCallback(() => {
    if (silenceTimerRef.current !== null) {
      clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (maxTimerRef.current !== null) {
      clearTimeout(maxTimerRef.current);
      maxTimerRef.current = null;
    }
  }, []);

  const endSession = useCallback(() => {
    shouldContinueRef.current = false;
    clearTimers();
    setIsListening(false);
    try {
      recognitionRef.current?.stop();
    } catch {
      /* already stopped */
    }
    recognitionRef.current = null;
  }, [clearTimers]);

  /** 20s without newly recognized speech ends the session (armed at start and refreshed on each onresult). */
  const armSilenceDeadline = useCallback(() => {
    if (!shouldContinueRef.current) return;
    if (silenceTimerRef.current !== null) {
      clearTimeout(silenceTimerRef.current);
    }
    silenceTimerRef.current = setTimeout(() => {
      silenceTimerRef.current = null;
      if (shouldContinueRef.current) endSession();
    }, SILENCE_MS);
  }, [endSession]);

  const startRecognitionInstance = useCallback(() => {
    const w = window as WindowWithSpeech;
    const SpeechRecognition = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!SpeechRecognition || !shouldContinueRef.current) return;

    const elapsed = Date.now() - sessionStartedAtRef.current;
    if (elapsed >= MAX_SESSION_MS) {
      endSession();
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      setIsListening(true);
    };

    recognition.onresult = (event: SpeechRecognitionResultEvent) => {
      armSilenceDeadline();
      let piece = '';
      for (let i = 0; i < event.results.length; i++) {
        piece += event.results[i][0].transcript;
      }
      piece = piece.trim();
      const prefix = committedPrefixRef.current.trimEnd();
      const full = prefix && piece ? `${prefix} ${piece}` : prefix || piece;
      lastFullTranscriptRef.current = full;
      const last = event.results[event.results.length - 1];
      callbacksRef.current.onTranscript({
        transcript: full,
        isFinal: last?.isFinal ?? false,
      });
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === 'aborted') return;
      if (event.error === 'not-allowed') {
        shouldContinueRef.current = false;
        clearTimers();
        setIsListening(false);
        callbacksRef.current.onError?.('Microphone permission denied. Please use text input.');
        recognitionRef.current = null;
        return;
      }
    };

    recognition.onend = () => {
      if (!shouldContinueRef.current) {
        recognitionRef.current = null;
        return;
      }
      const elapsed = Date.now() - sessionStartedAtRef.current;
      if (elapsed >= MAX_SESSION_MS) {
        endSession();
        return;
      }
      committedPrefixRef.current = lastFullTranscriptRef.current;
      setTimeout(() => {
        if (!shouldContinueRef.current) return;
        const e = Date.now() - sessionStartedAtRef.current;
        if (e >= MAX_SESSION_MS) {
          endSession();
          return;
        }
        startRecognitionRef.current();
      }, RESTART_DEBOUNCE_MS);
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
    } catch {
      endSession();
    }
  }, [armSilenceDeadline, clearTimers, endSession]);

  useEffect(() => {
    startRecognitionRef.current = () => {
      startRecognitionInstance();
    };
  }, [startRecognitionInstance]);

  const startListening = useCallback(() => {
    if (!isVoiceSupported()) {
      onError?.('Speech recognition not supported in this browser');
      return;
    }

    clearTimers();
    shouldContinueRef.current = true;
    sessionStartedAtRef.current = Date.now();
    committedPrefixRef.current = '';
    lastFullTranscriptRef.current = '';

    maxTimerRef.current = setTimeout(() => {
      maxTimerRef.current = null;
      if (shouldContinueRef.current) endSession();
    }, MAX_SESSION_MS);

    armSilenceDeadline();

    startRecognitionInstance();
  }, [armSilenceDeadline, clearTimers, endSession, onError, startRecognitionInstance]);

  const stopListening = useCallback(() => {
    endSession();
  }, [endSession]);

  return {
    isListening,
    startListening,
    stopListening,
    isSupported: isVoiceSupported(),
  };
}
