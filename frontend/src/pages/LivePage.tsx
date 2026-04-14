import { useEffect, useMemo, useRef, useState } from 'react';
import { Square } from 'lucide-react';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { TravelSettingsBar } from '@/components/chat/TravelSettingsBar';

import { useLiveSession } from '@/hooks/useLiveSession';
import { chatService, type ChatRequest } from '@/services/api';
import { useAuthStore, useChatStore } from '@/store';

export function LivePage() {
  const [text, setText] = useState('');
  const [thinkingDots, setThinkingDots] = useState(1);
  const [isGeneratingPlan, setIsGeneratingPlan] = useState(false);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);
  const navigate = useNavigate();
  const token = useAuthStore(s => s.token);
  const travelSettings = useChatStore(s => s.travelSettings);

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

  const canGeneratePlan = useMemo(() => {
    if (!token) return false;
    if (status !== 'connected') return false;
    if (isModelResponding || isRecording || isGeneratingPlan) return false;
    if (!text.trim()) return false;
    if (!travelSettings.destination || !travelSettings.start_date || !travelSettings.end_date)
      return false;
    return true;
  }, [
    token,
    status,
    isModelResponding,
    isRecording,
    isGeneratingPlan,
    text,
    travelSettings.destination,
    travelSettings.start_date,
    travelSettings.end_date,
  ]);

  const handleGeneratePlan = async () => {
    const prompt = text.trim();
    if (!prompt) return;
    if (!token) {
      toast.error('Please sign in to save a trip plan.');
      navigate('/login');
      return;
    }
    if (!canGeneratePlan) return;

    setIsGeneratingPlan(true);
    try {
      const prefs = {
        travel_style: travelSettings.travel_style,
        dietary_restriction: travelSettings.dietary_restriction,
        hotel_tier: travelSettings.hotel_tier,
        budget_min_hkd: travelSettings.budget_min_hkd,
        budget_max_hkd: travelSettings.budget_max_hkd,
        max_flight_stops: travelSettings.max_flight_stops,
      };

      const req: ChatRequest = {
        message: prompt,
        generate_plan: true,
        trip_parameters: {
          destination: travelSettings.destination,
          start_date: travelSettings.start_date,
          end_date: travelSettings.end_date,
          group_type: travelSettings.group_type,
          group_size: travelSettings.group_size,
          purpose: travelSettings.purpose,
        },
        user_preferences: prefs,
      };

      const res = await chatService.sendMessage(req);
      setText('');
      toast.success('Trip plan generated and saved!');
      navigate('/trips');
      // Also show a short confirmation in the transcript panel
      // (no need to inject the full itinerary here; Trips page is the source of truth).
    } catch (e) {
      const msg =
        e && typeof e === 'object' && 'detail' in e
          ? String((e as any).detail)
          : 'Failed to generate plan';
      toast.error(msg);
    } finally {
      setIsGeneratingPlan(false);
    }
  };

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
                <TravelSettingsBar />
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
                    <div className="flex items-center gap-2 shrink-0">
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
                      <Button
                        variant="secondary"
                        className="shrink-0"
                        onClick={handleGeneratePlan}
                        disabled={!canGeneratePlan}
                        title={
                          token
                            ? 'Generate a trip plan and save it to Trips'
                            : 'Sign in to generate and save trip plans'
                        }
                      >
                        {isGeneratingPlan ? 'Generating…' : 'Generate plan'}
                      </Button>
                    </div>
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
