// ChatPage — Main chat UI with AI travel agent

import { InputBar } from '@/components/chat/InputBar';
import { TravelSettingsBar } from '@/components/chat/TravelSettingsBar';
import { AttractionCard } from '@/components/trip/AttractionCard';
import { FlightCard } from '@/components/trip/FlightCard';
import { HotelCard } from '@/components/trip/HotelCard';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { isTTSAvailable, useTTS } from '@/hooks/useTTS';
import { chatSessionsService } from '@/services/api';
import { tripService } from '@/services/tripService';
import { useChatStore } from '@/store';
import type { DayPlan, Flight, TripItinerary } from '@/types/trip';
import {
  Banknote,
  Bed,
  Calendar,
  MapPin,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Plane,
  PlusCircle,
  Sparkles,
  Square,
  Ticket,
  Trash2,
  Volume2,
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { useNavigate } from 'react-router-dom';
import remarkGfm from 'remark-gfm';
import { toast } from 'sonner';

// Dynamic thinking placeholder that cycles based on elapsed time
const THINKING_MESSAGES = [
  { threshold: 0, text: 'Thinking...' },
  { threshold: 3000, text: 'Thinking really hard...' },
  { threshold: 8000, text: 'Searching the web...' },
  { threshold: 15000, text: 'Finding the best deals...' },
  { threshold: 25000, text: 'Checking flight prices...' },
  { threshold: 35000, text: 'Looking up hotels...' },
  { threshold: 50000, text: 'Almost there...' },
];

function useDynamicThinking(isLoading: boolean, hasMessages: boolean): string {
  const [message, setMessage] = useState(THINKING_MESSAGES[0].text);
  const startTimeRef = useRef<number | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (isLoading && !hasMessages) {
      // Start timing when loading begins with no messages
      if (startTimeRef.current === null) {
        startTimeRef.current = Date.now();
      }

      if (!intervalRef.current) {
        intervalRef.current = setInterval(() => {
          if (startTimeRef.current === null) return;
          const elapsed = Date.now() - startTimeRef.current;

          // Find the most recent matching threshold
          let current = THINKING_MESSAGES[0].text;
          for (const { threshold, text } of THINKING_MESSAGES) {
            if (elapsed >= threshold) {
              current = text;
            }
          }
          setMessage(current);
        }, 2000);
      }
    } else {
      // Reset when loading stops
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      startTimeRef.current = null;
      setMessage(THINKING_MESSAGES[0].text);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [isLoading, hasMessages]);

  return message;
}

/** Renders partial thought text with a blinking cursor typewriter effect */
function StreamingThought({ text, done }: { text: string; done: boolean }) {
  const [displayLength, setDisplayLength] = useState(0);
  const textRef = useRef(text);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  textRef.current = text;

  useEffect(() => {
    setDisplayLength(0);
    if (intervalRef.current) clearInterval(intervalRef.current);

    intervalRef.current = setInterval(() => {
      setDisplayLength(prev => {
        const remaining = textRef.current.length - prev;
        if (remaining <= 0) {
          if (intervalRef.current) clearInterval(intervalRef.current);
          return prev;
        }
        if (done) return prev + 10;
        if (remaining > 200) return prev + 3;
        return prev + 1;
      });
    }, 20);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [done]);

  useEffect(() => {
    setDisplayLength(prev => {
      const max = textRef.current.length;
      return prev >= max ? max : prev;
    });
  }, [text]);

  return (
    <>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text.slice(0, displayLength)}</ReactMarkdown>
      {displayLength < text.length && (
        <span className="inline-block w-0.5 h-3 bg-yellow-500 ml-0.5 animate-blink align-middle" />
      )}
    </>
  );
}

function StreamingMessage({
  content,
  isDone,
  onComplete,
}: {
  content: string;
  isDone?: boolean;
  onComplete?: () => void;
}) {
  const [displayLength, setDisplayLength] = useState(0);
  const contentRef = useRef(content);
  const lastUpdateRef = useRef(Date.now());
  const isDoneRef = useRef(false);
  const onCompleteRef = useRef(onComplete);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const hasCompletedRef = useRef(false);

  // Always keep refs in sync (but DON'T reset isDoneRef here - it tracks prop changes)
  contentRef.current = content;
  onCompleteRef.current = onComplete;

  useEffect(() => {
    lastUpdateRef.current = Date.now();
    hasCompletedRef.current = false;
    // Only reset isDoneRef on mount, not on every isDone prop change
    isDoneRef.current = false;

    // Start or restart the interval
    if (intervalRef.current) clearInterval(intervalRef.current);

    intervalRef.current = setInterval(() => {
      setDisplayLength(prev => {
        const remaining = contentRef.current.length - prev;
        if (remaining <= 0) {
          if (intervalRef.current) clearInterval(intervalRef.current);
          // Signal completion once finished
          if (!hasCompletedRef.current) {
            hasCompletedRef.current = true;
            onCompleteRef.current?.();
          }
          return prev;
        }
        // Always use typewriter effect — no jumping even when done streaming.
        // This ensures a smooth reveal regardless of how fast chunks arrived.
        // Once the full response is received (isDone=true), finish at max speed.
        if (isDoneRef.current) {
          return prev + 10;
        }
        if (remaining > 500) {
          // Large remaining content - speed up significantly
          return prev + 10;
        }
        if (remaining > 200) {
          // Moderate content - speed up moderately
          return prev + 3;
        }
        return prev + 1;
      });
    }, 20);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  // Update isDoneRef when isDone prop changes (separate effect to avoid interval restart)
  useEffect(() => {
    isDoneRef.current = isDone ?? false;
  }, [isDone]);

  const isStreaming = displayLength < content.length;

  return (
    <>
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content.slice(0, displayLength)}</ReactMarkdown>
      {isStreaming && (
        <span className="inline-block w-0.5 h-4 bg-yellow-500 ml-0.5 animate-blink align-middle" />
      )}
    </>
  );
}

// Inline Itinerary Display — shown after demo or LLM-generated trip
function ItineraryDisplay({
  itinerary,
  isGenerated,
}: {
  itinerary: TripItinerary;
  isGenerated?: boolean;
}) {
  const hotel = itinerary.hotels?.[0];
  const budget = itinerary.estimated_total_budget_hkd;

  const formatRange = (range?: { min: number; max: number }) => {
    if (!range) return 'N/A';
    if (range.min === range.max) return `HKD ${range.min.toLocaleString()}`;
    return `HKD ${range.min.toLocaleString()} - ${range.max.toLocaleString()}`;
  };

  return (
    <div className="w-full max-w-3xl mx-auto bg-white rounded-3xl border border-slate-100 shadow-xl overflow-hidden">
      {/* Header */}
      <div className="bg-linear-to-r from-slate-900 to-slate-800 p-8 text-white">
        <div className="flex items-center gap-2 text-blue-400 mb-4 font-black text-[10px] uppercase tracking-[0.3em]">
          <Sparkles className="size-4" /> {isGenerated ? 'Your Trip Plan' : 'Demo Trip Generated'}
        </div>
        <h2 className="text-4xl font-black tracking-tight mb-4">{itinerary.destination}</h2>
        <div className="flex items-center gap-4 text-sm text-slate-400">
          <span className="flex items-center gap-1">
            <Calendar className="size-3.5" />
            {itinerary.duration_days} days
          </span>
          <span className="flex items-center gap-1">
            <MapPin className="size-3.5" />
            {itinerary.flights?.length || 0} flights
          </span>
        </div>
      </div>

      <div className="p-8 space-y-8">
        {/* Summary */}
        {itinerary.summary && (
          <div className="bg-slate-50 rounded-2xl p-6 border border-slate-100 italic text-slate-600 text-lg">
            "{itinerary.summary}"
          </div>
        )}

        {/* Weather Tip */}
        {itinerary.weather_summary && (
          <div className="bg-blue-50 rounded-2xl p-5 border border-blue-100 flex gap-4 items-start">
            <div className="bg-blue-600 text-white px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest whitespace-nowrap h-fit">
              Travel Tip
            </div>
            <p className="text-xs text-blue-800 leading-relaxed">{itinerary.weather_summary}</p>
          </div>
        )}

        {/* Budget Section */}
        {budget && (
          <div>
            <div className="flex items-center gap-4 mb-6">
              <h3 className="text-xs font-black uppercase tracking-widest text-slate-400">
                Estimated Budget
              </h3>
              <div className="h-px flex-1 bg-slate-100" />
            </div>
            <div className="bg-white border border-slate-100 rounded-[2rem] p-8 shadow-sm">
              {/* Total */}
              <div className="flex items-center justify-between gap-6 mb-8 border-b border-slate-50 pb-8">
                <div className="flex items-center gap-4">
                  <div className="size-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center shadow-inner">
                    <Banknote className="size-6" />
                  </div>
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest mb-1 text-slate-400">
                      Total Trip Estimate
                    </p>
                    <p className="text-3xl font-black text-slate-900 tracking-tighter">
                      {formatRange(budget.total_hkd)}
                    </p>
                  </div>
                </div>
              </div>
              {/* Breakdown Grid */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-blue-50 text-blue-600 rounded-xl">
                    <Plane className="size-5" />
                  </div>
                  <div>
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                      Flights
                    </p>
                    <p className="font-bold text-slate-700">{formatRange(budget.flights_hkd)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-purple-50 text-purple-600 rounded-xl">
                    <Bed className="size-5" />
                  </div>
                  <div>
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                      Hotels
                    </p>
                    <p className="font-bold text-slate-700">{formatRange(budget.hotels_hkd)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-orange-50 text-orange-600 rounded-xl">
                    <Ticket className="size-5" />
                  </div>
                  <div>
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                      Activities
                    </p>
                    <p className="font-bold text-slate-700">{formatRange(budget.activities_hkd)}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Flights */}
        {itinerary.flights && itinerary.flights.length > 0 && (
          <div>
            <div className="flex items-center gap-4 mb-6">
              <h3 className="text-xs font-black uppercase tracking-widest text-slate-400">
                Flight Logistics
              </h3>
              <div className="h-px flex-1 bg-slate-100" />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {itinerary.flights.map((f: Flight, i: number) => (
                <FlightCard key={i} flight={f} />
              ))}
            </div>
          </div>
        )}

        {/* Days */}
        <div>
          <div className="flex items-center gap-4 mb-10">
            <h3 className="text-xs font-black uppercase tracking-widest text-slate-400">
              Daily Schedule
            </h3>
            <div className="h-px flex-1 bg-slate-100" />
          </div>
          <div className="space-y-12">
            {itinerary.days?.map((day: DayPlan) => (
              <div key={day.day_number}>
                {/* Day Header with theme and daily budget */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
                  <div className="flex items-center gap-4">
                    <div className="size-12 rounded-2xl bg-slate-900 text-white flex items-center justify-center font-black text-lg shadow-xl shrink-0">
                      {day.day_number}
                    </div>
                    <div>
                      <h4 className="font-black text-xl text-slate-900 leading-none">
                        Day {day.day_number}
                        {day.theme ? `: ${day.theme}` : ''}
                      </h4>
                      <p className="text-xs text-slate-400 font-bold uppercase tracking-widest mt-1.5">
                        {day.date}
                      </p>
                    </div>
                  </div>
                  {/* Daily Budget Badge */}
                  {day.estimated_daily_budget_hkd && (
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-50 rounded-xl border border-emerald-100 shrink-0 self-start sm:self-auto">
                      <Banknote className="size-4 text-emerald-600" />
                      <span className="text-[10px] font-black text-emerald-700 uppercase tracking-widest">
                        {formatRange(day.estimated_daily_budget_hkd)}
                      </span>
                    </div>
                  )}
                </div>
                <div className="ml-2 border-l-2 border-slate-50 pl-2">
                  <AttractionCard activity={day.morning?.[0]} label="Morning" />
                  <AttractionCard activity={day.afternoon?.[0]} label="Afternoon" />
                  <AttractionCard activity={day.evening?.[0]} label="Evening" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Hotel - use HotelCard for richer display */}
        {hotel && <HotelCard hotel={hotel} />}
      </div>
    </div>
  );
}

// Loading skeleton while demo generates
function DemoLoadingSkeleton() {
  return (
    <div className="w-full max-w-3xl mx-auto bg-white rounded-3xl border border-slate-100 shadow-xl overflow-hidden">
      <div className="bg-linear-to-r from-slate-900 to-slate-800 p-8">
        <div className="h-4 w-32 bg-white/10 rounded mb-4 animate-pulse" />
        <div className="h-10 w-64 bg-white/10 rounded animate-pulse" />
      </div>
      <div className="p-8 space-y-6">
        <div className="h-20 bg-slate-50 rounded-2xl animate-pulse" />
        <div className="h-32 bg-slate-50 rounded-2xl animate-pulse" />
        <div className="h-48 bg-slate-50 rounded-2xl animate-pulse" />
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start animate-in fade-in slide-in-from-bottom-2 duration-300">
      <div className="max-w-[72%] rounded-2xl px-5 py-4 bg-muted rounded-bl-md flex items-center gap-1.5 shadow-sm border border-border/50">
        <span
          className="size-2 bg-slate-400 rounded-full animate-bounce"
          style={{ animationDelay: '0ms' }}
        />
        <span
          className="size-2 bg-slate-400 rounded-full animate-bounce"
          style={{ animationDelay: '150ms' }}
        />
        <span
          className="size-2 bg-slate-400 rounded-full animate-bounce"
          style={{ animationDelay: '300ms' }}
        />
      </div>
    </div>
  );
}

export function ChatPage() {
  const navigate = useNavigate();
  const messages = useChatStore(s => s.messages);
  const isLoading = useChatStore(s => s.isLoading);
  const thinkingSteps = useChatStore(s => s.thinkingSteps);
  const partialThoughtText = useChatStore(s => s.partialThoughtText);
  const isLoggedIn = !!localStorage.getItem('access_token');
  const clearMessages = useChatStore(s => s.clearMessages);
  const sessionId = useChatStore(s => s.sessionId);
  const setSessionId = useChatStore(s => s.setSessionId);
  const setMessages = useChatStore(s => s.setMessages);
  const setForceNewSessionNextMessage = useChatStore(s => s.setForceNewSessionNextMessage);
  const abortController = useChatStore(s => s.abortController);

  const [sessions, setSessions] = useState<
    Array<{ id: number; title: string; created_at: string | null }>
  >([]);
  const [historyCollapsed, setHistoryCollapsed] = useState(false);
  const [editingSidebarSessionId, setEditingSidebarSessionId] = useState<number | null>(null);
  const [titleDraft, setTitleDraft] = useState('');

  const [demoItinerary, setDemoItinerary] = useState<TripItinerary | null>(null);
  const [showDemoLoading, setShowDemoLoading] = useState(false);
  // LLM-generated plan state (separate from demo)
  const [generatedItinerary, setGeneratedItinerary] = useState<TripItinerary | null>(null);
  const [showGeneratedLoading, setShowGeneratedLoading] = useState(false);
  const [clearAllHistoryDialogOpen, setClearAllHistoryDialogOpen] = useState(false);
  // Track when the last streaming message has finished typing
  const [typewriterDone, setTypewriterDone] = useState(false);
  const [speakingMsgId, setSpeakingMsgId] = useState<string | null>(null);
  const ttsAvailable = isTTSAvailable();
  const { isSpeaking, speak, stop } = useTTS({
    onEnd: () => setSpeakingMsgId(null),
    onError: () => setSpeakingMsgId(null),
  });
  // Set of user message IDs whose thinking bubble is expanded
  const [expandedBubbles, setExpandedBubbles] = useState<Set<string>>(new Set());

  const dynamicThinkingMessage = useDynamicThinking(isLoading, messages.length > 0);

  const currentSessionPk = useMemo(() => {
    const n = Number(sessionId);
    return Number.isFinite(n) ? n : null;
  }, [sessionId]);

  const currentSession = useMemo(
    () => (currentSessionPk ? sessions.find(s => s.id === currentSessionPk) : undefined),
    [currentSessionPk, sessions]
  );

  // Guard ref to prevent double-create within the same mount cycle (e.g., StrictMode)
  const createdRef = useRef(false);

  useEffect(() => {
    if (!isLoggedIn) return;

    (async () => {
      try {
        // Always fetch sessions list to show in sidebar
        const listRes = await chatSessionsService.list();
        setSessions(listRes.sessions);

        // Only create new session if we haven't already created one in this mount cycle
        // (prevents double-create from StrictMode) AND sessionId is null
        // (handles case where user navigates away and back - we fetch but don't create)
        if (createdRef.current || sessionId !== null) return;
        createdRef.current = true;

        const created = await chatSessionsService.create();
        setSessions(prev => [
          { id: created.session_id, title: created.title, created_at: created.created_at },
          ...prev,
        ]);
        setSessionId(String(created.session_id));
      } catch {
        // Best-effort — don't block chat UI if history load fails.
      }
    })();
  }, [isLoggedIn]);

  const startNewChat = async () => {
    // Cancel any in-progress stream first
    if (abortController) {
      abortController.abort();
    }
    clearMessages();
    useChatStore.setState({ thinkingSteps: [] });
    setDemoItinerary(null);
    setShowDemoLoading(false);
    setGeneratedItinerary(null);
    setShowGeneratedLoading(false);
    setTypewriterDone(false);
    if (isLoggedIn) {
      try {
        const created = await chatSessionsService.create();
        setSessions(prev => [
          { id: created.session_id, title: created.title, created_at: created.created_at },
          ...prev,
        ]);
        setSessionId(String(created.session_id));
      } catch {
        // Fallback: create on first message if create endpoint fails
        setSessionId(null);
        setForceNewSessionNextMessage(true);
      }
    } else {
      // Guest history UI not implemented yet; keep existing behavior.
      setSessionId(null);
      localStorage.removeItem('guest_uid');
    }
  };

  const loadSession = async (id: number) => {
    if (!isLoggedIn) return;

    // Cancel any in-progress stream first
    if (abortController) {
      abortController.abort();
    }

    // Immediately reset UI state before async ops to prevent stale render
    clearMessages();
    setTypewriterDone(false);
    setDemoItinerary(null);
    setShowDemoLoading(false);
    setGeneratedItinerary(null);
    setShowGeneratedLoading(false);
    useChatStore.getState().setThinking(false);
    useChatStore.getState().setPartialThoughtText('');
    useChatStore.setState({ thinkingSteps: [] });

    const res = await chatSessionsService.getMessages(id);
    setSessionId(String(id));
    setMessages(
      res.messages
        .filter(m => m.message_type !== 'tool_result') // exclude persisted tool results (not user-visible)
        .map(m => ({
          id: String(m.id),
          role: m.role as 'user' | 'assistant',
          content: m.content,
          timestamp: m.created_at ? new Date(m.created_at).getTime() : Date.now(),
          messageType: m.message_type,
          thinking_steps: m.thinking_steps,
        }))
    );
    setTypewriterDone(true);
  };

  const beginSidebarRename = (id: number, current: string) => {
    setEditingSidebarSessionId(id);
    setTitleDraft(current);
  };

  const commitRename = async (id: number) => {
    const next = titleDraft.trim();
    if (!next) {
      setEditingSidebarSessionId(null);
      return;
    }
    const updated = await chatSessionsService.rename(id, next);
    setSessions(prev => prev.map(s => (s.id === id ? { ...s, title: updated.title } : s)));
    setEditingSidebarSessionId(null);
  };

  const deleteSession = async (id: number) => {
    if (!isLoggedIn) return;
    const ok = window.confirm('Delete this chat? This cannot be undone.');
    if (!ok) return;

    try {
      await chatSessionsService.delete(id);
    } catch (e) {
      const err = e as any;
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail;
      console.error('Failed to delete session:', { status, detail, err });
      alert(
        `Failed to delete this chat. ${
          status ? `HTTP ${status}. ` : ''
        }${typeof detail === 'string' ? detail : 'Please try again.'}`
      );
      return;
    }

    // Compute next session from the *updated* list to avoid stale state bugs.
    let nextId: number | null = null;
    setSessions(prev => {
      const nextList = prev.filter(s => s.id !== id);
      nextId = nextList[0]?.id ?? null;
      return nextList;
    });

    if (currentSessionPk === id) {
      clearMessages();
      useChatStore.setState({ thinkingSteps: [] });
      setSessionId(null);
      if (nextId !== null) {
        await loadSession(nextId);
      }
    }
  };

  const handleClearAllHistory = async () => {
    if (!isLoggedIn) return;
    try {
      await chatSessionsService.clearAllHistory();
      setSessions([]);
      clearMessages();
      useChatStore.setState({ thinkingSteps: [] });
      setSessionId(null);
      toast.success('All chat history cleared');
    } catch (e) {
      const err = e as any;
      toast.error(err?.response?.data?.detail ?? 'Failed to clear chat history');
    }
  };

  // @ts-expect-error — temporarily hidden with button; restore together
  const _generateDemoTrip = async () => {
    if (showDemoLoading || isLoading) return;
    setShowDemoLoading(true);
    setDemoItinerary(null);
    try {
      const demo = await tripService.getDemoTrip();
      setDemoItinerary(demo.itinerary);
    } catch (err) {
      console.error('Failed to load demo trip:', err);
      alert('Demo trip not available. Please ensure the database is seeded.');
    } finally {
      setShowDemoLoading(false);
    }
  };

  // Track loading state for typewriter reset
  const prevLoadingRef = useRef(isLoading);
  useEffect(() => {
    if (isLoading && !prevLoadingRef.current) {
      // Loading started — reset typewriter and expanded bubbles
      setTypewriterDone(false);
      setExpandedBubbles(new Set());
    }
    prevLoadingRef.current = isLoading;
  }, [isLoading]);

  return (
    <div className="flex h-screen bg-background">
      {/* Left sidebar: Chat History (auth only) */}
      {isLoggedIn && (
        <aside
          className={`${historyCollapsed ? 'w-12' : 'w-72'} border-r bg-background flex flex-col transition-[width] duration-200`}
        >
          <div className={`${historyCollapsed ? 'px-2' : 'px-4'} py-4 border-b`}>
            <div
              className={`flex items-center ${historyCollapsed ? 'justify-center' : 'justify-between'} gap-2`}
            >
              {!historyCollapsed && (
                <div className="flex items-center justify-between w-full">
                  <div>
                    <div className="text-sm font-semibold">Chat History</div>
                    <div className="text-xs text-muted-foreground">Your sessions</div>
                  </div>
                  {sessions.length > 0 && isLoggedIn && (
                    <button
                      type="button"
                      onClick={() => setClearAllHistoryDialogOpen(true)}
                      className="flex items-center gap-1.5 h-7 rounded-lg border border-destructive/50 text-destructive hover:bg-destructive/10 px-2 text-xs font-medium transition-colors"
                      title="Clear all chat history"
                    >
                      <Trash2 className="size-3.5" />
                      Clear all
                    </button>
                  )}
                </div>
              )}
              <button
                type="button"
                onClick={() => setHistoryCollapsed(v => !v)}
                className="flex items-center justify-center h-8 w-8 rounded-xl border border-border bg-background text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                aria-label={historyCollapsed ? 'Expand chat history' : 'Collapse chat history'}
                title={historyCollapsed ? 'Expand' : 'Collapse'}
              >
                {historyCollapsed ? (
                  <PanelLeftOpen className="size-4" />
                ) : (
                  <PanelLeftClose className="size-4" />
                )}
              </button>
            </div>
          </div>

          {!historyCollapsed && (
            <div className="flex-1 overflow-y-auto p-2 space-y-1">
              {sessions.map(s => {
                const active = currentSessionPk === s.id;
                const isSidebarEditing = editingSidebarSessionId === s.id;
                return (
                  <div
                    key={s.id}
                    className={`group rounded-xl border px-3 py-2 text-sm transition-colors cursor-pointer ${
                      active
                        ? 'bg-muted border-slate-300 shadow-sm'
                        : 'bg-background hover:bg-muted/40 border-slate-200'
                    }`}
                    onClick={() => {
                      if (isSidebarEditing || editingSidebarSessionId) return;
                      console.log('[ChatPage] Clicked session:', { id: s.id, title: s.title });
                      loadSession(s.id);
                    }}
                  >
                    <div className="flex items-center gap-2">
                      {isSidebarEditing ? (
                        <input
                          className="h-7 flex-1 rounded-md border border-input bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring"
                          value={titleDraft}
                          onChange={e => setTitleDraft(e.target.value)}
                          onKeyDown={e => {
                            if (e.key === 'Enter') commitRename(s.id);
                            if (e.key === 'Escape') setEditingSidebarSessionId(null);
                          }}
                          autoFocus
                        />
                      ) : (
                        <span className="flex-1 text-left truncate" title={s.title}>
                          {s.title}
                        </span>
                      )}

                      {!isSidebarEditing && (
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            className="text-muted-foreground hover:text-foreground"
                            onClick={e => {
                              e.stopPropagation();
                              beginSidebarRename(s.id, s.title);
                            }}
                            aria-label="Rename chat"
                            type="button"
                          >
                            <Pencil className="size-3.5" />
                          </button>
                          <button
                            className="text-muted-foreground hover:text-destructive"
                            onClick={e => {
                              e.stopPropagation();
                              deleteSession(s.id);
                            }}
                            aria-label="Delete chat"
                            type="button"
                          >
                            <Trash2 className="size-3.5" />
                          </button>
                        </div>
                      )}
                    </div>
                    {s.created_at && (
                      <div className="mt-1 text-[11px] text-muted-foreground">
                        {new Date(s.created_at).toLocaleString()}
                      </div>
                    )}
                  </div>
                );
              })}
              {sessions.length === 0 && (
                <div className={`p-3 text-xs text-muted-foreground`}>
                  No sessions yet. Click New Chat to start.
                </div>
              )}
            </div>
          )}
        </aside>
      )}

      {/* Main chat area */}
      <main className="flex flex-col flex-1">
        {/* Header */}
        <header className="flex items-center gap-3 px-6 py-4 border-b">
          <div className="flex items-center justify-center rounded-xl bg-black text-white size-8">
            <MessageSquare className="size-4" />
          </div>
          <div className="min-w-0">
            <h1 className="text-sm font-semibold">GoGoGo</h1>
            <div className="flex items-center gap-2">
              {isLoggedIn && currentSessionPk && currentSession ? (
                <p
                  className={`text-xs text-muted-foreground truncate max-w-[${historyCollapsed ? '300px' : '130px'}]`}
                >
                  {currentSession.title}
                </p>
              ) : (
                <p className="text-xs text-muted-foreground">AI Travel Agent</p>
              )}
            </div>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={startNewChat}
              className="flex items-center gap-1.5 h-8 rounded-xl border border-border bg-background px-3 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            >
              <PlusCircle className="size-3" />
              New Chat
            </button>
            {/* TODO(temp-hidden): Demo Trip button temporarily hidden — uncomment to re-enable */}
            {/* <button
              onClick={generateDemoTrip}
              disabled={isLoading || showDemoLoading}
              className="flex items-center gap-1.5 h-8 rounded-xl bg-linear-to-r from-blue-600 to-blue-500 text-white px-3 text-xs font-medium hover:from-blue-500 hover:to-blue-400 transition-colors disabled:opacity-50"
            >
              <Sparkles className="size-3" />
              {showDemoLoading ? 'Generating...' : 'Demo Trip'}
            </button> */}
          </div>
        </header>

        {/* Message list */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
          {messages.length === 0 && !isLoading && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
              <div className="flex items-center justify-center rounded-full bg-muted size-12">
                <MessageSquare className="size-5 text-muted-foreground" />
              </div>
              <div>
                <p className="text-sm font-medium">Start your trip planning</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Ask me anything about destinations, flights, hotels, or attractions
                </p>
              </div>
              {!isLoggedIn && (
                <button
                  onClick={() => navigate('/login')}
                  className="h-8 rounded-xl bg-black text-white px-4 text-sm font-medium hover:opacity-80 transition-opacity"
                >
                  Sign in
                </button>
              )}
            </div>
          )}

          {isLoading && messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
              <div className="flex items-center justify-center rounded-full bg-muted size-12 animate-pulse">
                <MessageSquare className="size-5 text-muted-foreground" />
              </div>
              <p className="text-sm text-muted-foreground">{dynamicThinkingMessage}</p>
            </div>
          )}

          {/* Render messages as pairs: user message, thinking bubble, assistant response */}
          {Array.from({ length: Math.ceil(messages.length / 2) }).map((_, pairIdx) => {
            const userMsg = messages[pairIdx * 2];
            const assistantMsg = messages[pairIdx * 2 + 1];
            const isLastPair = pairIdx * 2 + 1 >= messages.length;
            const isStreamingAssistant =
              isLastPair && assistantMsg?.role === 'assistant' && !typewriterDone;

            if (!userMsg || userMsg.role !== 'user') return null;

            // Get thinking data for this exchange
            const hasLoadedThinkingSteps =
              Array.isArray(assistantMsg?.thinking_steps) && assistantMsg.thinking_steps.length > 0;
            const hasLiveThinkingSteps = thinkingSteps.length > 0;
            const hasPartialThinking = partialThoughtText.length > 0;

            // Show thinking bubble ALWAYS for every user message (persistent)
            // Show "Thinking..." if waiting for response OR if there's thinking content
            const hasThinkingContent =
              hasLoadedThinkingSteps || hasLiveThinkingSteps || hasPartialThinking;
            // For the last pair, show bubble while waiting for LLM response
            const isWaitingForResponse = isLastPair && isLoading && !assistantMsg;
            // Differentiate: "Thinking..." while waiting, "Thinking process" after LLM finished, "No thinking process available" if none
            const thinkingLabel = isWaitingForResponse
              ? 'Thinking...'
              : hasThinkingContent
                ? 'Thinking process'
                : 'No thinking process available';

            // Get thinking steps: prefer DB steps, fall back to live steps
            const thinkingStepsToShow =
              assistantMsg?.thinking_steps ?? (hasLiveThinkingSteps ? thinkingSteps : []);

            return (
              <div key={userMsg.id} className="space-y-4">
                {/* User message */}
                <div className="flex justify-end">
                  <div className="max-w-[72%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm bg-black text-white rounded-br-md">
                    {userMsg.content}
                  </div>
                </div>

                {/* Thinking bubble - ALWAYS shown for every user message */}
                <div className="flex justify-start">
                  <div className="max-w-[72%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm bg-muted text-foreground rounded-bl-md">
                    <button
                      onClick={() =>
                        setExpandedBubbles(prev => {
                          const next = new Set(prev);
                          if (next.has(userMsg.id)) {
                            next.delete(userMsg.id);
                          } else {
                            next.add(userMsg.id);
                          }
                          return next;
                        })
                      }
                      className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer"
                    >
                      <span>💭 {thinkingLabel}</span>
                      <span
                        className={`transition-transform ${expandedBubbles.has(userMsg.id) ? 'rotate-90' : ''}`}
                      >
                        ▶
                      </span>
                    </button>
                    {expandedBubbles.has(userMsg.id) &&
                      (hasThinkingContent || isWaitingForResponse) && (
                        <div className="mt-2 space-y-1 pt-2 border-t border-muted-foreground/20">
                          {thinkingStepsToShow.map((step, i) => (
                            <div key={i} className="text-xs text-muted-foreground leading-relaxed">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>{step}</ReactMarkdown>
                            </div>
                          ))}
                          {isWaitingForResponse && partialThoughtText && (
                            <div className="text-xs text-muted-foreground leading-relaxed">
                              <StreamingThought text={partialThoughtText} done={!isLoading} />
                            </div>
                          )}
                        </div>
                      )}
                  </div>
                </div>

                {/* Assistant response */}
                {assistantMsg && assistantMsg.role === 'assistant' && (
                  <div className="flex justify-start">
                    <div className="max-w-[72%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm bg-muted text-foreground rounded-bl-md">
                      {isStreamingAssistant ? (
                        <StreamingMessage
                          content={assistantMsg.content}
                          isDone={!isLoading}
                          onComplete={() => setTypewriterDone(true)}
                        />
                      ) : assistantMsg.messageType === 'error' ? (
                        <div className="flex items-start gap-2 text-red-600">
                          <span className="text-red-500 mt-0.5">⚠</span>
                          <div>
                            <p className="font-semibold text-red-600 text-xs uppercase tracking-wide mb-1">
                              Error
                            </p>
                            <p className="text-red-700 text-sm">{assistantMsg.content}</p>
                          </div>
                        </div>
                      ) : assistantMsg.messageType === 'itinerary' ? (
                        // Itinerary is rendered as a card below via demoItinerary state.
                        // Show a subtle inline indicator here instead of raw text.
                        <div className="flex items-center gap-2 text-muted-foreground text-xs italic">
                          <span>✨</span>
                          <span>Your trip plan is ready below</span>
                        </div>
                      ) : (
                        <div>
                          <div className="prose prose-sm dark:prose-invert max-w-none">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {assistantMsg.content}
                            </ReactMarkdown>
                          </div>
                          {ttsAvailable && assistantMsg.content.trim() && (
                            <div className="mt-2 flex justify-end">
                              <button
                                type="button"
                                className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background/60 px-2 py-1 text-xs text-muted-foreground hover:text-foreground hover:bg-background transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                                disabled={isStreamingAssistant}
                                aria-label={
                                  speakingMsgId === assistantMsg.id && isSpeaking
                                    ? 'Stop speaking'
                                    : 'Play text-to-speech'
                                }
                                onClick={() => {
                                  if (speakingMsgId === assistantMsg.id && isSpeaking) {
                                    stop();
                                    setSpeakingMsgId(null);
                                    return;
                                  }
                                  setSpeakingMsgId(assistantMsg.id);
                                  speak(assistantMsg.content);
                                }}
                              >
                                {speakingMsgId === assistantMsg.id && isSpeaking ? (
                                  <>
                                    <Square className="size-3" />
                                    Stop
                                  </>
                                ) : (
                                  <>
                                    <Volume2 className="size-3" />
                                    Play
                                  </>
                                )}
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* Typing indicator when waiting for assistant response */}
                {!assistantMsg && isLoading && isLastPair && <TypingIndicator />}
              </div>
            );
          })}

          {/* Demo trip result — shown inline after generation */}
          {showDemoLoading && <DemoLoadingSkeleton />}

          {demoItinerary && (
            <div className="flex justify-start">
              <ItineraryDisplay itinerary={demoItinerary} />
            </div>
          )}

          {/* LLM-generated trip result — shown inline after streaming */}
          {showGeneratedLoading && !generatedItinerary && <DemoLoadingSkeleton />}

          {generatedItinerary && (
            <div className="flex justify-start">
              <ItineraryDisplay itinerary={generatedItinerary} isGenerated />
            </div>
          )}
        </div>

        {/* Input bar */}
        <TravelSettingsBar />
        <InputBar
          onItinerary={setGeneratedItinerary}
          onFinalizing={() => setShowGeneratedLoading(true)}
          onTripSaved={() => toast.success('Trip saved!')}
        />

        {/* Clear all history confirmation */}
        <ConfirmDialog
          open={clearAllHistoryDialogOpen}
          onOpenChange={setClearAllHistoryDialogOpen}
          title="Clear all chat history"
          description="Are you sure you want to delete all your chat sessions? This cannot be undone."
          confirmLabel="Clear all"
          cancelLabel="Cancel"
          onConfirm={handleClearAllHistory}
          destructive
        />
      </main>
    </div>
  );
}
