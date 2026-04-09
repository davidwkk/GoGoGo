import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

export type LiveStatus = 'idle' | 'connecting' | 'connected' | 'error';

export interface LiveTranscriptItem {
  id: string;
  role: 'user' | 'model' | 'system';
  text: string;
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

export function useLiveSession() {
  const [status, setStatus] = useState<LiveStatus>('idle');
  const [lastError, setLastError] = useState<string | null>(null);
  const [transcripts, setTranscripts] = useState<LiveTranscriptItem[]>([]);
  const [isRecording, setIsRecording] = useState(false);
  const [isModelResponding, setIsModelResponding] = useState(false);
  /**
   * Track how many user turns we submitted vs how many the server finished.
   * Stale `turn_complete` after Stop is ignored for UI busy state.
   */
  const sentTurnsRef = useRef(0);
  const completedTurnsRef = useRef(0);
  /** After Stop, allow sending the next question even if the server turn is still finishing. */
  const userUnlockedAfterStopRef = useRef(false);

  const wsRef = useRef<WebSocket | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const playheadRef = useRef<number>(0);
  /** After user clicks Stop, drop audio chunks until the server finishes the turn. */
  const discardAudioUntilTurnCompleteRef = useRef(false);
  const isRecordingRef = useRef(false);
  /** If the model never sends audio/transcript, unlock the UI after this delay. */
  const stallTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const micStreamRef = useRef<MediaStream | null>(null);
  const micSourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const micProcessorRef = useRef<ScriptProcessorNode | null>(null);

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
    setTranscripts(prev => {
      const last = prev[prev.length - 1];
      if (last && last.role === role) {
        const merged = mergeStreamingTranscript(last.text, text);
        const display = role === 'model' ? normalizeModelTranscriptDisplay(merged) : merged;
        return [...prev.slice(0, -1), { ...last, text: display }];
      }
      const display = role === 'model' ? normalizeModelTranscriptDisplay(text) : text;
      return [...prev, { id: crypto.randomUUID(), role, text: display }];
    });
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current) return;
    clearStallTimer();
    setLastError(null);
    setStatus('connecting');
    setIsModelResponding(false);
    sentTurnsRef.current = 0;
    completedTurnsRef.current = 0;
    userUnlockedAfterStopRef.current = false;
    discardAudioUntilTurnCompleteRef.current = false;
    try {
      const wsUrl =
        (import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1')
          .replace(/^http/, 'ws')
          .replace(/\/$/, '') + '/live/ws';
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onopen = () => setStatus('connected');
      ws.onerror = () => {
        setStatus('error');
        setLastError('Live connection error');
      };
      ws.onclose = () => {
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
      };
      ws.onmessage = evt => {
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
  }, [applyTranscriptChunk, clearStallTimer, refreshRespondingUi, stopAudio, stopMic]);

  const disconnect = useCallback(() => {
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
  }, [clearStallTimer, stopAudio, stopMic]);

  const clear = useCallback(() => setTranscripts([]), []);

  const sendText = useCallback(
    (text: string) => {
      const t = text.trim();
      if (!t) return;
      const pending = sentTurnsRef.current > completedTurnsRef.current;
      if (pending && !userUnlockedAfterStopRef.current) return;
      userUnlockedAfterStopRef.current = false;
      sentTurnsRef.current += 1;
      discardAudioUntilTurnCompleteRef.current = false;
      setTranscripts(prev => [...prev, { id: crypto.randomUUID(), role: 'user', text: t }]);
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

      processor.onaudioprocess = ev => {
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
    ]
  );
}
