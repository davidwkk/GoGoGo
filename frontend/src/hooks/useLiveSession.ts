import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from 'react';

import { useChatStore } from '@/store';

export type LiveStatus = 'idle' | 'connecting' | 'connected' | 'error';

export interface LiveTranscriptItem {
  id: string;
  role: 'user' | 'model' | 'system';
  text: string;
}

export interface UseLiveSessionOptions {
  /** When this changes, the WebSocket is closed and audio/mic state is reset (switching live sections). */
  sectionKey: string;
  transcripts: LiveTranscriptItem[];
  setTranscripts: Dispatch<SetStateAction<LiveTranscriptItem[]>>;
}

type ServerMsg =
  | { type: 'audio'; data: string; mimeType?: string | null }
  | { type: 'transcript'; role: 'user' | 'model' | 'system'; text: string }
  | { type: 'turn_complete' }
  | { type: 'error'; message?: string }
  | { type: 'pong' };

function collapseInnerWhitespace(s: string): string {
  return s.replace(/\s+/g, ' ').trim();
}

/**
 * Gemini Live output_transcription sometimes omits spaces (words/punctuation run together).
 * Light cleanup for display — does not guess arbitrary word boundaries.
 */
function normalizeModelTranscriptDisplay(text: string): string {
  // If the model is emitting structured output, do NOT try to "fix spacing".
  // Live transcripts can include JSON/code fences; punctuation spacing can corrupt JSON.
  const trimmed = text.trimStart();
  if (trimmed.startsWith('{') || trimmed.startsWith('[') || trimmed.includes('```')) {
    return text;
  }

  let s = text;
  for (let i = 0; i < 6; i++) {
    const before = s;
    s = s.replace(/,([^\s\d])/g, ', $1');
    s = s.replace(/\.([^\s\d])/g, '. $1');
    s = s.replace(/\?([^\s])/g, '? $1');
    s = s.replace(/!([^\s])/g, '! $1');
    s = s.replace(/([a-z])([A-Z])/g, '$1 $2');
    s = s.replace(/\b(large)(language)(model)\b/gi, '$1 $2 $3');
    s = s.replace(/\b(language)(model)\b/gi, '$1 $2');
    s = s.replace(/\b(trained)(by)\b/gi, '$1 $2');
    s = s.replace(/\b(there)(anything)\b/gi, '$1 $2');
    s = s.replace(/\b(there)(something)\b/gi, '$1 $2');
    s = s.replace(/\b(something)(specific)\b/gi, '$1 $2');
    s = s.replace(/\b(anything)(specific)\b/gi, '$1 $2');
    s = s.replace(/\b(specific)(you)/gi, '$1 $2');
    s = s.replace(/\b(you)('d|'ll|'re|'ve)\b/gi, '$1$2');
    s = s.replace(/\b(you)(would|will)\b/gi, '$1 $2');
    s = s.replace(/\b(like)(to)\b/gi, '$1 $2');
    s = s.replace(/\b(know)(about)\b/gi, '$1 $2');
    s = s.replace(/\b(about)(me)\b/gi, '$1 $2');
    s = s.replace(/\b(about)(it)\b/gi, '$1 $2');
    s = s.replace(/\b(is)(there)\b/gi, '$1 $2');
    s = s.replace(/\b(I'm)\s+a([a-z]{2,})\b/gi, "I'm a $1");
    s = s.replace(/\bI'm([a-z]{4,})\b/gi, "I'm $1");
    if (s === before) break;
  }
  return s;
}

/** Longest suffix of `a` that equals prefix of `b` (for stitching stream chunks). */
function longestOverlapSuffixPrefix(a: string, b: string): number {
  const max = Math.min(a.length, b.length);
  for (let k = max; k >= 1; k--) {
    if (a.slice(-k) === b.slice(0, k)) return k;
  }
  return 0;
}

/**
 * Merge streaming transcript fragments from Gemini Live.
 * Handles cumulative text, token deltas, and duplicate "I'm …" restarts mid-stream.
 */
function mergeStreamingTranscript(prev: string, incoming: string): string {
  const p = prev.trimEnd();
  let n = incoming.trim();
  if (!n) return prev;
  if (!p) return incoming;

  const pC = collapseInnerWhitespace(p);
  let nC = collapseInnerWhitespace(n);

  if (nC.startsWith(pC)) {
    return incoming.length >= prev.length ? incoming : prev;
  }
  if (pC.startsWith(nC)) return prev;
  if (incoming.startsWith(prev) || n.startsWith(p)) {
    return incoming.length >= prev.length ? incoming : prev;
  }
  if (prev.startsWith(n)) return prev;
  if (p.endsWith(n)) return prev;
  if (n.endsWith(p)) return incoming;

  if (/\bI'm\b/i.test(p) && /^I'm[^'\s]/i.test(n) && !nC.startsWith(pC)) {
    const stripped = n.replace(/^I'm\s*(a\s*)?/i, '').trimStart();
    if (stripped.length > 0 && stripped.length < n.length) {
      n = stripped;
      nC = collapseInnerWhitespace(n);
      if (nC.startsWith(pC)) {
        return incoming.length >= prev.length ? incoming : prev;
      }
    }
  }

  const overlap = longestOverlapSuffixPrefix(p, n);
  if (overlap > 0) {
    return p + n.slice(overlap);
  }

  const needSpace = !/\s$/.test(p) && !/^\s/.test(n);
  return p + (needSpace ? ' ' : '') + n;
}

function base64FromBytes(bytes: Uint8Array): string {
  let bin = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    bin += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(bin);
}

function bytesFromBase64(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function int16FromBytesLE(bytes: Uint8Array): Int16Array {
  return new Int16Array(bytes.buffer, bytes.byteOffset, Math.floor(bytes.byteLength / 2));
}

function downsampleTo16k(input: Float32Array, inRate: number): Int16Array {
  const outRate = 16000;
  if (inRate === outRate) {
    const out = new Int16Array(input.length);
    for (let i = 0; i < input.length; i++) {
      const s = Math.max(-1, Math.min(1, input[i]));
      out[i] = (s * 0x7fff) | 0;
    }
    return out;
  }

  const ratio = inRate / outRate;
  const outLen = Math.floor(input.length / ratio);
  const out = new Int16Array(outLen);
  for (let i = 0; i < outLen; i++) {
    const idx = Math.floor(i * ratio);
    const s = Math.max(-1, Math.min(1, input[idx] ?? 0));
    out[i] = (s * 0x7fff) | 0;
  }
  return out;
}

function ensurePlaybackContext(audioCtxRef: MutableRefObject<AudioContext | null>) {
  if (!audioCtxRef.current) {
    audioCtxRef.current = new AudioContext({ sampleRate: 24000 });
    return audioCtxRef.current;
  }
  return audioCtxRef.current;
}

export function useLiveSession({ sectionKey, transcripts, setTranscripts }: UseLiveSessionOptions) {
  const [status, setStatus] = useState<LiveStatus>('idle');
  const [lastError, setLastError] = useState<string | null>(null);
  const [isRecording, setIsRecording] = useState(false);
  const [isModelResponding, setIsModelResponding] = useState(false);

  const setTranscriptsRef = useRef(setTranscripts);
  setTranscriptsRef.current = setTranscripts;

  const sentTurnsRef = useRef(0);
  const completedTurnsRef = useRef(0);
  const userUnlockedAfterStopRef = useRef(false);

  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const playheadRef = useRef<number>(0);
  const discardAudioUntilTurnCompleteRef = useRef(false);
  const isRecordingRef = useRef(false);
  const stallTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const manualDisconnectRef = useRef(false);
  const sessionIdRef = useRef<string>('');
  const connectRef = useRef<(() => void) | null>(null);

  const micStreamRef = useRef<MediaStream | null>(null);
  const micSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const micProcessorRef = useRef<ScriptProcessorNode | null>(null);

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  }, []);

  const stopAudio = useCallback(() => {
    try {
      audioCtxRef.current?.close();
    } catch {
      /* ignore */
    }
    audioCtxRef.current = null;
    playheadRef.current = 0;
  }, []);

  const stopMic = useCallback(() => {
    try {
      micProcessorRef.current?.disconnect();
    } catch {
      /* ignore */
    }
    try {
      micSourceRef.current?.disconnect();
    } catch {
      /* ignore */
    }

    micProcessorRef.current = null;
    micSourceRef.current = null;

    const stream = micStreamRef.current;
    if (stream) {
      for (const t of stream.getTracks()) t.stop();
    }
    micStreamRef.current = null;
  }, []);

  const wsSend = useCallback((payload: unknown) => {
    const ws = wsRef.current;
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify(payload));
  }, []);

  const clearStallTimer = useCallback(() => {
    if (stallTimerRef.current) {
      clearTimeout(stallTimerRef.current);
      stallTimerRef.current = null;
    }
  }, []);

  const scheduleStallWatchdog = useCallback(() => {
    clearStallTimer();
    stallTimerRef.current = setTimeout(() => {
      stallTimerRef.current = null;
      if (sentTurnsRef.current <= completedTurnsRef.current) return;
      if (userUnlockedAfterStopRef.current) return;
      setLastError(
        'No reply after 90s. Check API key and network; if you use a SOCKS proxy for the backend, set LLM_PROXY_ENABLED=0 for Live.'
      );
      userUnlockedAfterStopRef.current = true;
      setIsModelResponding(false);
    }, 90_000);
  }, [clearStallTimer]);

  const refreshRespondingUi = useCallback(() => {
    const pending = sentTurnsRef.current > completedTurnsRef.current;
    const showBusy = pending && !userUnlockedAfterStopRef.current;
    setIsModelResponding(showBusy);
  }, []);

  const stopResponse = useCallback(() => {
    clearStallTimer();
    discardAudioUntilTurnCompleteRef.current = true;
    stopAudio();
    userUnlockedAfterStopRef.current = true;
    setIsModelResponding(false);
  }, [clearStallTimer, stopAudio]);

  const applyTranscriptChunk = useCallback((role: 'user' | 'model' | 'system', text: string) => {
    if (!text) return;
    setTranscriptsRef.current((prev: LiveTranscriptItem[]) => {
      const last = prev[prev.length - 1];
      // After optimistic text send, Gemini may echo the same user line via input_transcription — skip duplicate.
      if (role === 'user' && last?.role === 'user') {
        const a = collapseInnerWhitespace(last.text).toLowerCase();
        const b = collapseInnerWhitespace(text).toLowerCase();
        if (a === b) return prev;
      }
      if (last && last.role === role) {
        const merged = mergeStreamingTranscript(last.text, text);
        const display = role === 'model' ? normalizeModelTranscriptDisplay(merged) : merged;
        return [...prev.slice(0, -1), { ...last, text: display }];
      }
      const display = role === 'model' ? normalizeModelTranscriptDisplay(text) : text;
      return [...prev, { id: crypto.randomUUID(), role, text: display }];
    });
  }, []);

  const hardResetConnection = useCallback(() => {
    clearReconnectTimer();
    clearStallTimer();
    wsRef.current?.close();
    wsRef.current = null;
    stopMic();
    stopAudio();
    setIsRecording(false);
    isRecordingRef.current = false;
    setIsModelResponding(false);
    sentTurnsRef.current = 0;
    completedTurnsRef.current = 0;
    userUnlockedAfterStopRef.current = false;
    discardAudioUntilTurnCompleteRef.current = false;
    setStatus('idle');
  }, [clearReconnectTimer, clearStallTimer, stopAudio, stopMic]);

  useEffect(() => {
    // Stable session id per section. Used by backend to preserve context across reconnects.
    // Persisted so a refresh doesn't lose the "live session" continuity for this section.
    try {
      const key = `live_session_id:${sectionKey}`;
      const existing = localStorage.getItem(key);
      const sid = existing && existing.trim().length > 0 ? existing : crypto.randomUUID();
      localStorage.setItem(key, sid);
      sessionIdRef.current = sid;
    } catch {
      sessionIdRef.current = crypto.randomUUID();
    }

    hardResetConnection();
    return () => {
      hardResetConnection();
    };
  }, [sectionKey, hardResetConnection]);

  const connect = useCallback(() => {
    if (wsRef.current) return;
    clearStallTimer();
    clearReconnectTimer();
    manualDisconnectRef.current = false;
    setLastError(null);
    setStatus('connecting');
    setIsModelResponding(false);
    sentTurnsRef.current = 0;
    completedTurnsRef.current = 0;
    userUnlockedAfterStopRef.current = false;
    discardAudioUntilTurnCompleteRef.current = false;
    try {
      const live_model = useChatStore.getState().live_model;
      const live_voice = useChatStore.getState().live_voice;
      const sid = sessionIdRef.current || crypto.randomUUID();
      const voiceParam =
        live_voice && live_voice !== 'default' ? `&voice=${encodeURIComponent(live_voice)}` : '';
      const wsUrl =
        (
          ((import.meta as unknown as { env?: { VITE_API_URL?: string } }).env?.VITE_API_URL as
            | string
            | undefined) || 'http://localhost:8000/api/v1'
        )
          .replace(/^http/, 'ws')
          .replace(/\/$/, '') +
        `/live/ws?model=${encodeURIComponent(live_model)}&session_id=${encodeURIComponent(sid)}${voiceParam}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onopen = () => {
        if (wsRef.current !== ws) return;
        setStatus('connected');
        reconnectAttemptsRef.current = 0;
        const ctx = ensurePlaybackContext(audioCtxRef);
        void ctx.resume().catch(() => {});
      };
      ws.onerror = () => {
        if (wsRef.current !== ws) return;
        setStatus('error');
        setLastError('Live connection error');
      };
      ws.onclose = () => {
        if (wsRef.current !== ws) return;
        clearStallTimer();
        wsRef.current = null;
        stopMic();
        stopAudio();
        setIsRecording(false);
        isRecordingRef.current = false;
        setIsModelResponding(false);
        sentTurnsRef.current = 0;
        completedTurnsRef.current = 0;
        userUnlockedAfterStopRef.current = false;
        discardAudioUntilTurnCompleteRef.current = false;
        setStatus('idle');

        if (manualDisconnectRef.current) return;
        // Auto-reconnect with backoff (keeps transcripts in UI).
        const attempt = reconnectAttemptsRef.current + 1;
        reconnectAttemptsRef.current = attempt;
        const delay = Math.min(10_000, 500 * 2 ** Math.min(6, attempt)); // 1s..10s
        clearReconnectTimer();
        reconnectTimerRef.current = setTimeout(() => {
          reconnectTimerRef.current = null;
          connectRef.current?.();
        }, delay);
      };
      ws.onmessage = evt => {
        if (wsRef.current !== ws) return;
        try {
          const msg = JSON.parse(String(evt.data)) as ServerMsg;
          if (msg.type === 'transcript' && msg.text) {
            if (msg.role === 'model') clearStallTimer();
            applyTranscriptChunk(msg.role, msg.text);
            return;
          }
          if (msg.type === 'error') {
            clearStallTimer();
            setLastError(msg.message || 'Live error');
            sentTurnsRef.current = 0;
            completedTurnsRef.current = 0;
            userUnlockedAfterStopRef.current = false;
            setIsModelResponding(false);
            return;
          }
          if (msg.type === 'turn_complete') {
            clearStallTimer();
            discardAudioUntilTurnCompleteRef.current = false;
            completedTurnsRef.current += 1;
            userUnlockedAfterStopRef.current = false;
            refreshRespondingUi();
            return;
          }
          if (msg.type === 'audio' && msg.data) {
            clearStallTimer();
            if (discardAudioUntilTurnCompleteRef.current) return;

            const bytes = bytesFromBase64(msg.data);
            const pcm16 = int16FromBytesLE(bytes);
            const sampleRate = /rate=(\d+)/.exec(msg.mimeType || '')?.[1]
              ? Number(/rate=(\d+)/.exec(msg.mimeType || '')?.[1])
              : 24000;

            if (!audioCtxRef.current) {
              audioCtxRef.current = new AudioContext({ sampleRate });
              playheadRef.current = audioCtxRef.current.currentTime;
            }
            const ctx = audioCtxRef.current;
            if (!ctx) return;

            void ctx.resume().catch(() => {});

            const float = new Float32Array(pcm16.length);
            for (let i = 0; i < pcm16.length; i++) float[i] = pcm16[i] / 0x8000;
            const buf = ctx.createBuffer(1, float.length, sampleRate);
            buf.copyToChannel(float, 0);

            const src = ctx.createBufferSource();
            src.buffer = buf;
            src.connect(ctx.destination);

            const now = ctx.currentTime;
            const startAt = Math.max(now, playheadRef.current);
            src.start(startAt);
            playheadRef.current = startAt + buf.duration;
          }
        } catch (e) {
          setLastError(e instanceof Error ? e.message : 'Failed to parse Live message');
        }
      };
    } catch (e) {
      wsRef.current = null;
      setStatus('error');
      setLastError(e instanceof Error ? e.message : 'Failed to connect');
    }
  }, [
    applyTranscriptChunk,
    clearReconnectTimer,
    clearStallTimer,
    refreshRespondingUi,
    stopAudio,
    stopMic,
  ]);

  // Keep a stable ref to the latest connect() (for reconnect timer).
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  // Auto-connect when entering a live section.
  useEffect(() => {
    if (status === 'idle' && !wsRef.current) {
      connect();
    }
  }, [connect, status]);

  const disconnect = useCallback(() => {
    manualDisconnectRef.current = true;
    hardResetConnection();
  }, [hardResetConnection]);

  const clear = useCallback(() => {
    setTranscriptsRef.current([]);
  }, []);

  const sendText = useCallback(
    (text: string) => {
      const t = text.trim();
      if (!t) return;
      const pending = sentTurnsRef.current > completedTurnsRef.current;
      if (pending && !userUnlockedAfterStopRef.current) return;
      userUnlockedAfterStopRef.current = false;
      sentTurnsRef.current += 1;
      discardAudioUntilTurnCompleteRef.current = false;
      const ctx = ensurePlaybackContext(audioCtxRef);
      void ctx.resume().catch(() => {});

      setTranscriptsRef.current((prev: LiveTranscriptItem[]) => [
        ...prev,
        { id: crypto.randomUUID(), role: 'user', text: t },
      ]);
      refreshRespondingUi();
      scheduleStallWatchdog();
      wsSend({ type: 'text', text: t });
    },
    [refreshRespondingUi, scheduleStallWatchdog, wsSend]
  );

  const startRecording = useCallback(async () => {
    const pending = sentTurnsRef.current > completedTurnsRef.current;
    if (isRecording || (pending && !userUnlockedAfterStopRef.current)) return;
    if (status !== 'connected') {
      setLastError('Connect first');
      return;
    }

    setLastError(null);
    setIsRecording(true);
    isRecordingRef.current = true;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      micStreamRef.current = stream;

      const ctx = audioCtxRef.current || new AudioContext();
      audioCtxRef.current = ctx;
      await ctx.resume();

      const source = ctx.createMediaStreamSource(stream);
      micSourceRef.current = source;

      const processor = ctx.createScriptProcessor(4096, 1, 1);
      micProcessorRef.current = processor;

      processor.onaudioprocess = (ev: AudioProcessingEvent) => {
        if (!isRecordingRef.current) return;
        const input = ev.inputBuffer.getChannelData(0);
        const pcm16 = downsampleTo16k(input, ctx.sampleRate);
        const u8 = new Uint8Array(pcm16.buffer);
        const b64 = base64FromBytes(u8);
        wsSend({ type: 'audio', data: b64, mimeType: 'audio/pcm;rate=16000' });
      };

      source.connect(processor);
      processor.connect(ctx.destination);
    } catch (e) {
      setIsRecording(false);
      isRecordingRef.current = false;
      stopMic();
      wsSend({ type: 'audio_stream_end' });
      setLastError(e instanceof Error ? e.message : 'Microphone error');
    }
  }, [isRecording, status, stopMic, wsSend]);

  const stopRecording = useCallback(() => {
    if (!isRecording) return;
    setIsRecording(false);
    isRecordingRef.current = false;
    stopMic();
    userUnlockedAfterStopRef.current = false;
    sentTurnsRef.current += 1;
    discardAudioUntilTurnCompleteRef.current = false;
    refreshRespondingUi();
    scheduleStallWatchdog();
    wsSend({ type: 'audio_stream_end' });
  }, [isRecording, refreshRespondingUi, scheduleStallWatchdog, stopMic, wsSend]);

  useEffect(() => {
    if (status !== 'connected' && isRecording) {
      setIsRecording(false);
      isRecordingRef.current = false;
      stopMic();
    }
  }, [isRecording, status, stopMic]);

  return useMemo(
    () => ({
      status,
      transcripts,
      isRecording,
      isModelResponding,
      connect,
      disconnect,
      sendText,
      startRecording,
      stopRecording,
      stopResponse,
      clear,
      lastError,
    }),
    [
      transcripts,
      status,
      isRecording,
      isModelResponding,
      connect,
      disconnect,
      sendText,
      startRecording,
      stopRecording,
      stopResponse,
      clear,
      lastError,
    ]
  );
}
