import { useEffect, useMemo, useRef, useState } from 'react';
import { Square } from 'lucide-react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

import { useLiveSession } from '@/hooks/useLiveSession';
import { useChatStore } from '@/store';

const LIVE_MODELS: { value: string; label: string }[] = [
  { value: 'gemini-3.1-flash-live-preview', label: '3.1 Flash Live (Default)' },
  {
    value: 'gemini-2.5-flash-native-audio-preview-12-2025',
    label: '2.5 Flash Native Audio (Backup)',
  },
];

export function LivePage() {
  const [text, setText] = useState('');
  const [thinkingDots, setThinkingDots] = useState(1);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);

  const {
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
  } = useLiveSession();

  const live_model = useChatStore(s => s.live_model);
  const setLiveModel = useChatStore(s => s.setLiveModel);

  const handleModelChange = (val: string) => {
    const defaultModel = 'gemini-3.1-flash-live-preview';
    const userSelected = val !== defaultModel;
    console.log('[LivePage] model selected: %s | user_selected=%s', val, userSelected);
    setLiveModel(val);
  };

  useEffect(() => {
    if (lastError) toast.error(lastError);
  }, [lastError]);

  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcripts]);

  useEffect(() => {
    if (!isModelResponding) {
      setThinkingDots(1);
      return;
    }
    const id = window.setInterval(() => {
      setThinkingDots(d => (d >= 3 ? 1 : d + 1));
    }, 450);
    return () => window.clearInterval(id);
  }, [isModelResponding]);

  const canSend = useMemo(
    () => status === 'connected' && text.trim().length > 0 && !isModelResponding,
    [status, text, isModelResponding]
  );

  return (
    <div className="w-full h-full">
      <div className="mx-auto max-w-4xl px-6 py-8">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold">Live</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              One question at a time while the model speaks. Use Stop to end playback early;
              transcript keeps the full text.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Select value={live_model} onValueChange={handleModelChange}>
              <SelectTrigger className="w-[180px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {LIVE_MODELS.map(m => (
                  <SelectItem key={m.value} value={m.value}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {status !== 'connected' ? (
              <Button onClick={connect} disabled={status === 'connecting'}>
                {status === 'connecting' ? 'Connecting…' : 'Connect'}
              </Button>
            ) : (
              <Button variant="secondary" onClick={disconnect}>
                Disconnect
              </Button>
            )}
            <Button variant="ghost" onClick={clear} disabled={transcripts.length === 0}>
              Clear
            </Button>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Transcript</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-[420px] overflow-auto rounded-lg border bg-background p-3">
                {transcripts.length === 0 ? (
                  <div className="text-sm text-muted-foreground">No messages yet.</div>
                ) : (
                  <div className="space-y-3">
                    {transcripts.map(t => (
                      <div key={t.id} className="text-sm">
                        <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                          {t.role}
                        </div>
                        <div className="whitespace-pre-wrap">{t.text}</div>
                      </div>
                    ))}
                    <div ref={transcriptEndRef} />
                  </div>
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">Input</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-3">
                <div className="flex items-center gap-2">
                  <Input
                    value={text}
                    onChange={e => setText(e.target.value)}
                    placeholder={
                      status === 'connected'
                        ? isModelResponding
                          ? 'Thinking… or press Stop to cancel'
                          : 'Type a message…'
                        : 'Connect to start…'
                    }
                    disabled={status !== 'connected'}
                    onKeyDown={e => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        if (!canSend) return;
                        sendText(text.trim());
                        setText('');
                      }
                    }}
                  />
                  {isModelResponding ? (
                    <Button variant="destructive" onClick={stopResponse} className="shrink-0">
                      <Square className="size-3.5 mr-1.5" />
                      Stop
                    </Button>
                  ) : (
                    <Button
                      className="shrink-0"
                      onClick={() => {
                        if (!canSend) return;
                        sendText(text.trim());
                        setText('');
                      }}
                      disabled={!canSend}
                    >
                      Send
                    </Button>
                  )}
                </div>

                <div className="flex items-center gap-2">
                  <Button
                    variant={isRecording ? 'destructive' : 'default'}
                    disabled={status !== 'connected' || isModelResponding}
                    onClick={() => {
                      if (status !== 'connected' || isModelResponding) return;
                      if (isRecording) stopRecording();
                      else startRecording();
                    }}
                  >
                    {isRecording ? 'Stop talking' : 'Push to talk'}
                  </Button>
                  <div className="text-xs text-muted-foreground">
                    Status: <span className="font-medium">{status}</span>
                    {isModelResponding && (
                      <span className="text-foreground tabular-nums">
                        {' · Thinking'}
                        <span className="inline-block w-[1.1em] text-left">
                          {'.'.repeat(thinkingDots)}
                        </span>
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
