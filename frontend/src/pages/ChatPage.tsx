// ChatPage — Main chat UI with AI travel agent

import { InputBar } from '@/components/chat/InputBar';
import { TravelSettingsBar } from '@/components/chat/TravelSettingsBar';
import { AttractionCard } from '@/components/trip/AttractionCard';
import { FlightCard } from '@/components/trip/FlightCard';
import { HotelCard } from '@/components/trip/HotelCard';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import { useTTS } from '@/hooks/useTTS';
import { chatSessionsService, type ChatSessionListItem } from '@/services/api';
import { useAuthStore, useChatStore } from '@/store';
import type { DayPlan, Flight, TripItinerary } from '@/types/trip';
import DOMPurify from 'dompurify';
import {
  Banknote,
  Bed,
  Calendar,
  Copy,
  MapPin,
  Menu,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  Plane,
  PlusCircle,
  Sparkles,
  Square,
  Star,
  Ticket,
  Trash2,
  Volume2, // Added Menu icon for mobile sidebar toggle
  X, // Added X icon to close sidebar on mobile
} from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { useNavigate } from 'react-router-dom';
import remarkGfm from 'remark-gfm';
import { toast } from 'sonner';

function normalizeSessions(list: ChatSessionListItem[]): ChatSessionListItem[] {
  return list.map(s => ({ ...s, is_favorite: s.is_favorite ?? false }));
}

/** Favorites first, then newest by created_at. */
function sortSessionsForSidebar(sessions: ChatSessionListItem[]): ChatSessionListItem[] {
  return [...sessions].sort((a, b) => {
    const fa = a.is_favorite ? 1 : 0;
    const fb = b.is_favorite ? 1 : 0;
    if (fa !== fb) return fb - fa;
    const ta = a.created_at ? new Date(a.created_at).getTime() : 0;
    const tb = b.created_at ? new Date(b.created_at).getTime() : 0;
    return tb - ta;
  });
}

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
  const doneRef = useRef(done);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  textRef.current = text;

  // Keep track of the done state without restarting the interval
  useEffect(() => {
    doneRef.current = done;
  }, [done]);

  useEffect(() => {
    // Start or restart the interval
    if (intervalRef.current) clearInterval(intervalRef.current);

    intervalRef.current = setInterval(() => {
      setDisplayLength(prev => {
        const remaining = textRef.current.length - prev;

        // If we caught up to the current text...
        if (remaining <= 0) {
          // ONLY clear the interval if the stream is officially finished
          if (doneRef.current) {
            if (intervalRef.current) clearInterval(intervalRef.current);
          }
          // If not done, keep the interval alive and wait for the next chunk!
          return prev;
        }

        // Always use typewriter effect
        if (doneRef.current) return prev + 10;
        if (remaining > 500) return prev + 10;
        if (remaining > 200) return prev + 3;
        return prev + 1;
      });
    }, 20);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

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

        // If we caught up to the current text...
        if (remaining <= 0) {
          // ONLY clear the interval if the stream is officially finished
          if (isDoneRef.current) {
            if (intervalRef.current) clearInterval(intervalRef.current);
            // Signal completion once finished
            if (!hasCompletedRef.current) {
              hasCompletedRef.current = true;
              onCompleteRef.current?.();
            }
          }
          // If not done, keep the interval alive and wait for the next chunk!
          return prev;
        }

        // Always use typewriter effect — no jumping even when done streaming.
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

  const hasReturn = itinerary.flights?.some((f: Flight) => f.direction === 'return') ?? false;

  return (
    <div className="w-full max-w-3xl mx-auto bg-white rounded-3xl border border-slate-100 shadow-xl overflow-hidden">
      {/* Header */}
      <div className="bg-linear-to-r from-slate-900 to-slate-800 p-6 md:p-8 text-white">
        <div className="flex items-center gap-2 text-blue-400 mb-4 font-black text-[10px] uppercase tracking-[0.3em]">
          <Sparkles className="size-4" /> {isGenerated ? 'Your Trip Plan' : 'Demo Trip Generated'}
        </div>
        <h2 className="text-3xl md:text-4xl font-black tracking-tight mb-4">
          {itinerary.destination}
        </h2>
        <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-sm text-slate-400">
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

      <div className="p-6 md:p-8 space-y-8">
        {/* Summary */}
        {itinerary.summary && (
          <div className="bg-slate-50 rounded-2xl p-5 md:p-6 border border-slate-100 italic text-slate-600 text-base md:text-lg">
            "{itinerary.summary}"
          </div>
        )}

        {/* Weather Tip */}
        {itinerary.weather_summary && (
          <div className="bg-blue-50 rounded-2xl p-4 md:p-5 border border-blue-100 flex flex-col sm:flex-row gap-3 sm:gap-4 sm:items-start">
            <div className="bg-blue-600 text-white px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest whitespace-nowrap w-fit">
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
            <div className="bg-white border border-slate-100 rounded-[2rem] p-6 md:p-8 shadow-sm">
              {/* Total */}
              <div className="flex items-center justify-between gap-6 mb-6 md:mb-8 border-b border-slate-50 pb-6 md:pb-8">
                <div className="flex items-center gap-4">
                  <div className="size-10 md:size-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center shadow-inner shrink-0">
                    <Banknote className="size-5 md:size-6" />
                  </div>
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest mb-1 text-slate-400">
                      Total Trip Estimate
                    </p>
                    <p className="text-2xl md:text-3xl font-black text-slate-900 tracking-tighter">
                      {formatRange(budget.total_hkd)}
                    </p>
                  </div>
                </div>
              </div>
              {/* Breakdown Grid */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
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
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
              {itinerary.flights.map((f: Flight, i: number) => (
                <FlightCard key={i} flight={f} tripType={hasReturn ? 'round_trip' : 'one_way'} />
              ))}
            </div>
          </div>
        )}

        {/* Days */}
        <div>
          <div className="flex items-center gap-4 mb-8 md:mb-10">
            <h3 className="text-xs font-black uppercase tracking-widest text-slate-400">
              Daily Schedule
            </h3>
            <div className="h-px flex-1 bg-slate-100" />
          </div>
          <div className="space-y-10 md:space-y-12">
            {itinerary.days?.map((day: DayPlan) => (
              <div key={day.day_number}>
                {/* Day Header with theme and daily budget */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 md:mb-8">
                  <div className="flex items-center gap-4">
                    <div className="size-10 md:size-12 rounded-2xl bg-slate-900 text-white flex items-center justify-center font-black text-base md:text-lg shadow-xl shrink-0">
                      {day.day_number}
                    </div>
                    <div>
                      <h4 className="font-black text-lg md:text-xl text-slate-900 leading-tight md:leading-none">
                        Day {day.day_number}
                        {day.theme ? `: ${day.theme}` : ''}
                      </h4>
                      <p className="text-xs text-slate-400 font-bold uppercase tracking-widest mt-1 md:mt-1.5">
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
                <div className="ml-2 sm:ml-4 border-l-2 border-slate-50 pl-4 sm:pl-6">
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
      <div className="bg-linear-to-r from-slate-900 to-slate-800 p-6 md:p-8">
        <div className="h-4 w-32 bg-white/10 rounded mb-4 animate-pulse" />
        <div className="h-8 md:h-10 w-48 md:w-64 bg-white/10 rounded animate-pulse" />
      </div>
      <div className="p-6 md:p-8 space-y-6">
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
      <div className="max-w-[85%] md:max-w-[72%] rounded-2xl px-4 py-3 md:px-5 md:py-4 bg-muted rounded-bl-md flex items-center gap-1.5 shadow-sm border border-border/50">
        <span
          className="size-1.5 md:size-2 bg-slate-400 rounded-full animate-bounce"
          style={{ animationDelay: '0ms' }}
        />
        <span
          className="size-1.5 md:size-2 bg-slate-400 rounded-full animate-bounce"
          style={{ animationDelay: '150ms' }}
        />
        <span
          className="size-1.5 md:size-2 bg-slate-400 rounded-full animate-bounce"
          style={{ animationDelay: '300ms' }}
        />
      </div>
    </div>
  );
}

function MessageListSkeleton() {
  return (
    <div className="space-y-4 animate-in fade-in duration-300">
      <div className="flex justify-end">
        <div className="h-10 w-40 md:w-48 rounded-2xl bg-slate-200 animate-pulse rounded-br-md" />
      </div>
      <div className="flex justify-start">
        <div className="h-8 w-32 md:w-36 rounded-2xl bg-muted animate-pulse rounded-bl-md" />
      </div>
      <div className="flex justify-start">
        <div className="space-y-2">
          <div className="h-10 w-56 md:w-64 rounded-2xl bg-muted animate-pulse rounded-bl-md" />
          <div className="h-4 w-40 md:w-48 rounded bg-muted/70 animate-pulse ml-1" />
        </div>
      </div>
      <div className="flex justify-end mt-6">
        <div className="h-10 w-48 md:w-56 rounded-2xl bg-slate-200 animate-pulse rounded-br-md" />
      </div>
      <div className="flex justify-start">
        <div className="h-8 w-32 md:w-36 rounded-2xl bg-muted animate-pulse rounded-bl-md" />
      </div>
      <div className="flex justify-start">
        <div className="space-y-2">
          <div className="h-10 w-64 md:w-72 rounded-2xl bg-muted animate-pulse rounded-bl-md" />
          <div className="h-4 w-48 md:w-52 rounded bg-muted/70 animate-pulse ml-1" />
          <div className="h-4 w-36 md:w-40 rounded bg-muted/70 animate-pulse ml-1" />
        </div>
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
  const isLoggedIn = useAuthStore(s => !!s.token);
  const clearMessages = useChatStore(s => s.clearMessages);
  const sessionId = useChatStore(s => s.sessionId);
  const setSessionId = useChatStore(s => s.setSessionId);
  const setMessages = useChatStore(s => s.setMessages);
  const setForceNewSessionNextMessage = useChatStore(s => s.setForceNewSessionNextMessage);
  const abortController = useChatStore(s => s.abortController);

  const [sessions, setSessions] = useState<ChatSessionListItem[]>([]);
  const [historyCollapsed, setHistoryCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false); // Mobile sidebar state
  const [editingSidebarSessionId, setEditingSidebarSessionId] = useState<number | null>(null);
  const [titleDraft, setTitleDraft] = useState('');

  const [demoItinerary, setDemoItinerary] = useState<TripItinerary | null>(null);
  const [showDemoLoading, setShowDemoLoading] = useState(false);
  // LLM-generated plan state (separate from demo)
  const [generatedItinerary, setGeneratedItinerary] = useState<TripItinerary | null>(null);
  const [showGeneratedLoading, setShowGeneratedLoading] = useState(false);
  const [clearAllHistoryDialogOpen, setClearAllHistoryDialogOpen] = useState(false);
  const [deleteSessionDialogId, setDeleteSessionDialogId] = useState<number | null>(null);
  // Track when the last streaming message has finished typing
  const [typewriterDone, setTypewriterDone] = useState(false);
  const [speakingMsgId, setSpeakingMsgId] = useState<string | null>(null);
  const {
    isSpeaking,
    speak,
    stop,
    isAvailable: ttsAvailable,
  } = useTTS({
    onEnd: () => setSpeakingMsgId(null),
    onError: () => setSpeakingMsgId(null),
  });
  // Set of user message IDs whose thinking bubble is expanded
  const [expandedBubbles, setExpandedBubbles] = useState<Set<string>>(new Set());
  const [sessionError, setSessionError] = useState<string | null>(null);
  const [lastUserMessage, setLastUserMessage] = useState<string>('');
  const [sessionLoading, setSessionLoading] = useState(false);

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
    (async () => {
      try {
        // Always fetch sessions list to show in sidebar (works for both users + guests)
        let guestUid: string | null = null;
        if (!isLoggedIn) {
          guestUid = localStorage.getItem('guest_uid');
          if (!guestUid) {
            guestUid = crypto.randomUUID();
            localStorage.setItem('guest_uid', guestUid);
          }
        }

        const listRes = isLoggedIn
          ? await chatSessionsService.list()
          : await chatSessionsService.listGuest(guestUid!);
        setSessions(sortSessionsForSidebar(normalizeSessions(listRes.sessions)));

        // Only create new session if we haven't already created one in this mount cycle
        // (prevents double-create from StrictMode) AND sessionId is null
        // (handles case where user navigates away and back - we fetch but don't create)
        if (createdRef.current || sessionId !== null) return;
        createdRef.current = true;

        const created = isLoggedIn
          ? await chatSessionsService.create()
          : await chatSessionsService.createGuest(guestUid!);
        setSessions(prev =>
          sortSessionsForSidebar([
            {
              id: created.session_id,
              title: created.title,
              is_favorite: created.is_favorite ?? false,
              created_at: created.created_at,
            },
            ...prev,
          ])
        );
        setSessionId(String(created.session_id));
      } catch {
        // Best-effort — don't block chat UI if history load fails.
      }
    })();
  }, [isLoggedIn]);

  const startNewChat = async () => {
    // Cancel any in-progress stream / plan request first
    if (abortController) {
      abortController.abort();
    }
    useChatStore.getState().setLoading(false);
    useChatStore.getState().setThinking(false);
    useChatStore.getState().setPartialThoughtText('');
    useChatStore.getState().setAbortController(null);
    clearMessages();
    useChatStore.setState({ thinkingSteps: [] });
    setDemoItinerary(null);
    setShowDemoLoading(false);
    setGeneratedItinerary(null);
    setShowGeneratedLoading(false);
    setTypewriterDone(false);
    setMobileSidebarOpen(false); // Close mobile sidebar
    try {
      if (isLoggedIn) {
        const created = await chatSessionsService.create();
        setSessions(prev =>
          sortSessionsForSidebar([
            {
              id: created.session_id,
              title: created.title,
              is_favorite: created.is_favorite ?? false,
              created_at: created.created_at,
            },
            ...prev,
          ])
        );
        setSessionId(String(created.session_id));
        return;
      }

      // Guest: create a new guest session and keep guest_uid stable.
      let guestUid = localStorage.getItem('guest_uid');
      if (!guestUid) {
        guestUid = crypto.randomUUID();
        localStorage.setItem('guest_uid', guestUid);
      }
      const created = await chatSessionsService.createGuest(guestUid);
      setSessions(prev =>
        sortSessionsForSidebar([
          {
            id: created.session_id,
            title: created.title,
            is_favorite: created.is_favorite ?? false,
            created_at: created.created_at,
          },
          ...prev,
        ])
      );
      setSessionId(String(created.session_id));
    } catch {
      // Fallback: create on first message if create endpoint fails
      setSessionId(null);
      setForceNewSessionNextMessage(true);
    }
  };

  const loadSession = async (id: number) => {
    // Cancel any in-progress stream / plan request first
    if (abortController) {
      abortController.abort();
    }
    useChatStore.getState().setLoading(false);
    useChatStore.getState().setThinking(false);
    useChatStore.getState().setPartialThoughtText('');
    useChatStore.getState().setAbortController(null);

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
    setMobileSidebarOpen(false); // Close mobile sidebar

    setSessionError(null);
    setSessionLoading(true);
    try {
      let guestUid: string | null = null;
      if (!isLoggedIn) {
        guestUid = localStorage.getItem('guest_uid');
        if (!guestUid) {
          guestUid = crypto.randomUUID();
          localStorage.setItem('guest_uid', guestUid);
        }
      }
      const res = isLoggedIn
        ? await chatSessionsService.getMessages(id)
        : await chatSessionsService.getGuestMessages(id, guestUid!);
      setSessionId(String(id));
      setMessages(
        res.messages
          .filter(m => m.message_type !== 'tool_result')
          .map(m => ({
            id: String(m.id),
            role: m.role as 'user' | 'assistant',
            content: m.content,
            timestamp: m.created_at ? new Date(m.created_at).getTime() : Date.now(),
            messageType: m.message_type,
            thinking_steps: m.thinking_steps,
          }))
      );

      const itineraryMsg = res.messages.find(m => m.message_type === 'itinerary');
      if (itineraryMsg?.content) {
        try {
          const parsed = JSON.parse(itineraryMsg.content);
          if (parsed?.__type === 'itinerary' && parsed?.data) {
            setGeneratedItinerary(parsed.data as TripItinerary);
          }
        } catch {
          // ignore parse errors
        }
      }

      const assistantMsgWithThinking = res.messages.find(
        m =>
          m.role === 'assistant' && Array.isArray(m.thinking_steps) && m.thinking_steps.length > 0
      );
      if (assistantMsgWithThinking) {
        useChatStore.setState({ thinkingSteps: assistantMsgWithThinking.thinking_steps });
      }

      setTypewriterDone(true);
    } catch {
      setSessionError('Failed to load this chat. Please try again.');
    } finally {
      setSessionLoading(false);
    }
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
    let updated;
    if (isLoggedIn) {
      updated = await chatSessionsService.rename(id, next);
    } else {
      let guestUid = localStorage.getItem('guest_uid');
      if (!guestUid) {
        guestUid = crypto.randomUUID();
        localStorage.setItem('guest_uid', guestUid);
      }
      updated = await chatSessionsService.renameGuest(id, next, guestUid);
    }
    setSessions(prev =>
      sortSessionsForSidebar(
        prev.map(s =>
          s.id === id
            ? { ...s, title: updated.title, is_favorite: updated.is_favorite ?? s.is_favorite }
            : s
        )
      )
    );
    setEditingSidebarSessionId(null);
  };

  const toggleSessionFavorite = async (sessionPk: number, currentlyFavorite: boolean) => {
    const next = !currentlyFavorite;
    try {
      let updated: ChatSessionListItem;
      if (isLoggedIn) {
        updated = await chatSessionsService.patchSession(sessionPk, { is_favorite: next });
      } else {
        let guestUid = localStorage.getItem('guest_uid');
        if (!guestUid) {
          guestUid = crypto.randomUUID();
          localStorage.setItem('guest_uid', guestUid);
        }
        updated = await chatSessionsService.patchGuestSession(
          sessionPk,
          { is_favorite: next },
          guestUid
        );
      }
      setSessions(prev =>
        sortSessionsForSidebar(
          prev.map(s =>
            s.id === sessionPk ? { ...s, is_favorite: updated.is_favorite ?? next } : s
          )
        )
      );
    } catch {
      toast.error('Could not update favorite');
    }
  };

  const deleteSession = async (id: number) => {
    setDeleteSessionDialogId(id);
  };

  const handleDeleteConfirm = async () => {
    const id = deleteSessionDialogId;
    if (id === null) return;
    setDeleteSessionDialogId(null);

    try {
      if (isLoggedIn) {
        await chatSessionsService.delete(id);
      } else {
        let guestUid = localStorage.getItem('guest_uid');
        if (!guestUid) {
          guestUid = crypto.randomUUID();
          localStorage.setItem('guest_uid', guestUid);
        }
        await chatSessionsService.deleteGuest(id, guestUid);
      }
      toast.success('Chat deleted');
    } catch (e) {
      const err = e as { response?: { status?: number; data?: { detail?: string } } };
      const status = err.response?.status;
      const detail = err.response?.data?.detail;
      console.error('Failed to delete session:', { status, detail, err });
      toast.error(
        `Failed to delete this chat. ${
          status ? `HTTP ${status}. ` : ''
        }${typeof detail === 'string' ? detail : 'Please try again.'}`
      );
      return;
    }

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
    try {
      if (isLoggedIn) {
        await chatSessionsService.clearAllHistory();
      } else {
        let guestUid = localStorage.getItem('guest_uid');
        if (!guestUid) {
          guestUid = crypto.randomUUID();
          localStorage.setItem('guest_uid', guestUid);
        }
        await chatSessionsService.clearAllGuestHistory(guestUid);
      }
      setSessions([]);
      clearMessages();
      useChatStore.setState({ thinkingSteps: [] });
      setSessionId(null);
      toast.success('All chat history cleared');
    } catch (e) {
      const err = e as { response?: { data?: { detail?: string } } };
      toast.error(err.response?.data?.detail ?? 'Failed to clear chat history');
    }
  };

  const autoExpandedRef = useRef<string | null>(null);

  useEffect(() => {
    if (isLoading) {
      setTypewriterDone(false);
      const lastUser = [...messages].reverse().find(m => m.role === 'user');

      if (lastUser && autoExpandedRef.current !== lastUser.id) {
        setExpandedBubbles(new Set([lastUser.id]));
        autoExpandedRef.current = lastUser.id;
      }
    } else {
      setExpandedBubbles(new Set());
      autoExpandedRef.current = null;
    }
  }, [isLoading, messages]);

  useEffect(() => {
    if (!lastUserMessage) return;
    navigator.clipboard.writeText(lastUserMessage).catch(console.error);
    setLastUserMessage('');
    toast(
      'Message failed. Your message has been copied to your clipboard — just paste and try again.',
      {
        action: {
          label: 'OK',
          onClick: () => {},
        },
      }
    );
  }, [lastUserMessage]);

  return (
    <div className="flex h-screen bg-background overflow-hidden relative">
      {/* Mobile Sidebar Overlay */}
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setMobileSidebarOpen(false)}
        />
      )}

      {/* Left sidebar: Chat History */}
      <aside
        className={`
          fixed inset-y-0 left-0 z-50 transform transition-transform duration-300 ease-in-out
          md:relative md:translate-x-0
          ${mobileSidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          ${historyCollapsed ? 'md:w-0 md:border-r-0' : 'w-72 md:w-72 md:border-r'}
          bg-background flex flex-col overflow-hidden border-r shadow-2xl md:shadow-none
        `}
      >
        <div className="px-4 py-4 border-b flex-shrink-0 flex items-center justify-between">
          <div className="text-sm font-semibold">Chat History</div>
          <div className="flex items-center gap-2">
            {sessions.length > 0 && (
              <button
                type="button"
                onClick={() => setClearAllHistoryDialogOpen(true)}
                className="flex items-center gap-1.5 h-7 rounded-lg border border-destructive/50 text-destructive hover:bg-destructive/10 px-2 text-xs font-medium transition-colors"
                title="Clear all chat history"
              >
                <Trash2 className="size-3.5" />
                <span className="hidden sm:inline">Clear all</span>
              </button>
            )}

            {/* Close button for mobile */}
            <button
              type="button"
              onClick={() => setMobileSidebarOpen(false)}
              className="md:hidden flex items-center justify-center h-8 w-8 rounded-xl bg-background text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
              aria-label="Close sidebar"
            >
              <X className="size-4" />
            </button>

            {/* Collapse button for desktop */}
            <button
              type="button"
              onClick={() => setHistoryCollapsed(true)}
              className="hidden md:flex items-center justify-center h-8 w-8 rounded-xl border border-border bg-background text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
              aria-label="Collapse chat history"
              title="Collapse"
            >
              <PanelLeftClose className="size-4" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          <button
            onClick={startNewChat}
            className="w-full flex items-center justify-center gap-1.5 h-9 rounded-xl border border-border bg-background px-3 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
          >
            <PlusCircle className="size-3" />
            New Chat
          </button>
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
                  loadSession(s.id);
                }}
              >
                <div className="flex items-center gap-2">
                  {!isSidebarEditing && (
                    <button
                      type="button"
                      className={`shrink-0 rounded-md p-0.5 transition-colors hover:bg-muted/80 ${
                        s.is_favorite
                          ? 'text-amber-500'
                          : 'text-muted-foreground opacity-70 group-hover:opacity-100 md:opacity-0 md:group-hover:opacity-100'
                      }`}
                      onClick={e => {
                        e.stopPropagation();
                        void toggleSessionFavorite(s.id, s.is_favorite);
                      }}
                      aria-label={s.is_favorite ? 'Remove from favorites' : 'Add to favorites'}
                      title={s.is_favorite ? 'Remove from favorites' : 'Favorite'}
                    >
                      <Star className={`size-3.5 ${s.is_favorite ? 'fill-amber-400' : ''}`} />
                    </button>
                  )}
                  {isSidebarEditing ? (
                    <input
                      className="h-7 flex-1 rounded-md border border-input bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring min-w-0"
                      value={titleDraft}
                      onChange={e => setTitleDraft(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') commitRename(s.id);
                        if (e.key === 'Escape') setEditingSidebarSessionId(null);
                      }}
                      autoFocus
                    />
                  ) : (
                    <span className="flex-1 text-left truncate min-w-0" title={s.title}>
                      {s.title}
                    </span>
                  )}

                  {!isSidebarEditing && (
                    <div className="flex items-center gap-1 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
                      <button
                        className="text-muted-foreground hover:text-foreground p-1"
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
                        className="text-muted-foreground hover:text-destructive p-1"
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
                  <div className="mt-1 text-[11px] text-muted-foreground ml-6">
                    {new Date(s.created_at).toLocaleString(undefined, {
                      month: 'short',
                      day: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </div>
                )}
              </div>
            );
          })}
          {sessions.length === 0 && (
            <div className="p-3 text-xs text-muted-foreground text-center mt-4">
              {isLoggedIn
                ? 'No sessions yet. Click New Chat to start.'
                : 'Sign in to save your chat sessions.'}
            </div>
          )}
        </div>
      </aside>

      {/* Main chat area */}
      <main className="flex flex-col flex-1 min-w-0 bg-background relative">
        {/* Header */}
        <header
          className={`flex items-center gap-3 px-4 md:px-6 py-3 md:py-4 shrink-0 ${!historyCollapsed ? '' : 'border-b'} border-b md:border-b-0`}
        >
          {/* Mobile Menu Button */}
          <button
            type="button"
            onClick={() => setMobileSidebarOpen(true)}
            className="md:hidden flex items-center justify-center h-8 w-8 rounded-xl bg-background text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
            aria-label="Open sidebar"
          >
            <Menu className="size-5" />
          </button>

          {historyCollapsed && (
            <button
              type="button"
              onClick={() => setHistoryCollapsed(false)}
              className="hidden md:flex items-center justify-center h-8 w-8 rounded-xl border border-border bg-background text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors shrink-0"
              aria-label="Expand chat history"
              title="Expand"
            >
              <PanelLeftOpen className="size-4" />
            </button>
          )}

          {historyCollapsed && (
            <button
              onClick={startNewChat}
              className="hidden md:flex items-center gap-1.5 h-8 rounded-xl border border-border bg-background px-3 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors shrink-0"
            >
              <PlusCircle className="size-3" />
              New Chat
            </button>
          )}

          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              {currentSessionPk && currentSession ? (
                <p className="text-sm font-semibold text-foreground truncate">
                  {currentSession.title}
                </p>
              ) : (
                <p className="text-xs font-medium text-muted-foreground">AI Travel Agent</p>
              )}
            </div>
          </div>
        </header>

        {/* Message list */}
        <div className="flex-1 overflow-y-auto px-3 sm:px-6 py-4 sm:py-6 space-y-4">
          {/* Session loading skeleton */}
          {sessionLoading && <MessageListSkeleton />}

          {sessionError && !sessionLoading && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-4">
              <div className="flex items-center justify-center rounded-full bg-red-50 size-12 shrink-0">
                <MessageSquare className="size-5 text-red-400" />
              </div>
              <div>
                <p className="text-sm font-medium text-red-600">Failed to load chat</p>
                <p className="text-xs text-muted-foreground mt-0.5">{sessionError}</p>
              </div>
              <button
                onClick={() => currentSessionPk && loadSession(currentSessionPk)}
                className="h-8 rounded-xl bg-black text-white px-4 text-sm font-medium hover:opacity-80 transition-opacity"
              >
                Retry
              </button>
            </div>
          )}

          {!sessionLoading && messages.length === 0 && !isLoading && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center px-4">
              <div className="flex items-center justify-center rounded-full bg-muted size-12 shrink-0">
                <MessageSquare className="size-5 text-muted-foreground" />
              </div>
              <div>
                <p className="text-sm font-medium">Start your trip planning</p>
                <p className="text-xs text-muted-foreground mt-0.5 max-w-xs mx-auto">
                  Ask me anything about destinations, flights, hotels, or attractions
                </p>
              </div>
              {!isLoggedIn && (
                <button
                  onClick={() => navigate('/login')}
                  className="h-8 rounded-xl bg-black text-white px-4 text-sm font-medium hover:opacity-80 transition-opacity mt-2"
                >
                  Sign in
                </button>
              )}
            </div>
          )}

          {!sessionLoading && isLoading && messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
              <div className="flex items-center justify-center rounded-full bg-muted size-12 animate-pulse shrink-0">
                <MessageSquare className="size-5 text-muted-foreground" />
              </div>
              <p className="text-sm text-muted-foreground">{dynamicThinkingMessage}</p>
            </div>
          )}

          {!sessionLoading &&
            Array.from({ length: Math.ceil(messages.length / 2) }).map((_, pairIdx) => {
              const userMsg = messages[pairIdx * 2];
              const assistantMsg = messages[pairIdx * 2 + 1];
              const isLastPair = pairIdx === Math.ceil(messages.length / 2) - 1;
              const isStreamingAssistant =
                isLastPair &&
                assistantMsg?.role === 'assistant' &&
                !typewriterDone &&
                assistantMsg.messageType !== 'itinerary' &&
                assistantMsg.messageType !== 'error';

              if (!userMsg || userMsg.role !== 'user') return null;

              const hasLoadedThinkingSteps =
                Array.isArray(assistantMsg?.thinking_steps) &&
                assistantMsg.thinking_steps.length > 0;
              const hasLiveThinkingSteps = thinkingSteps.length > 0;
              const hasPartialThinking = partialThoughtText.length > 0;

              const hasThinkingContent =
                hasLoadedThinkingSteps || hasLiveThinkingSteps || hasPartialThinking;
              const isWaitingForResponse = isLastPair && isLoading && !assistantMsg;
              const thinkingLabel = isWaitingForResponse
                ? 'Thinking...'
                : hasThinkingContent
                  ? 'Thinking process'
                  : 'No thinking process available';

              const thinkingStepsToShow =
                assistantMsg?.thinking_steps ?? (hasLiveThinkingSteps ? thinkingSteps : []);

              return (
                <div key={userMsg.id} className="space-y-3 sm:space-y-4">
                  <div className="flex justify-end">
                    <div className="max-w-[90%] sm:max-w-[85%] md:max-w-[72%] rounded-2xl px-3 sm:px-4 py-2.5 sm:py-3 text-sm leading-relaxed shadow-sm bg-black text-white rounded-br-md whitespace-pre-wrap break-words">
                      {userMsg.content}
                    </div>
                  </div>

                  <div className="flex justify-start">
                    <div className="max-w-[90%] sm:max-w-[85%] md:max-w-[72%] rounded-2xl px-3 sm:px-4 py-2 sm:py-3 text-sm leading-relaxed shadow-sm bg-muted text-foreground rounded-bl-md">
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
                        className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors cursor-pointer py-1"
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
                          <div className="mt-2 space-y-1.5 pt-2 border-t border-muted-foreground/20 overflow-hidden">
                            {thinkingStepsToShow.map((step, i) => (
                              <div
                                key={i}
                                className="text-xs text-muted-foreground leading-relaxed animate-in fade-in slide-in-from-left-2 duration-300 break-words"
                              >
                                <ReactMarkdown remarkPlugins={[remarkGfm]}>{step}</ReactMarkdown>
                              </div>
                            ))}
                            {isWaitingForResponse && partialThoughtText && (
                              <div className="text-xs text-muted-foreground leading-relaxed break-words">
                                <StreamingThought text={partialThoughtText} done={!isLoading} />
                              </div>
                            )}
                          </div>
                        )}
                    </div>
                  </div>

                  {assistantMsg && assistantMsg.role === 'assistant' && (
                    <div className="flex justify-start">
                      <div className="max-w-[95%] sm:max-w-[85%] md:max-w-[72%] rounded-2xl px-3 sm:px-4 py-3 text-sm leading-relaxed shadow-sm bg-muted text-foreground rounded-bl-md overflow-x-hidden">
                        {isStreamingAssistant ? (
                          <div className="break-words">
                            <StreamingMessage
                              content={assistantMsg.content}
                              isDone={!isLoading}
                              onComplete={() => setTypewriterDone(true)}
                            />
                          </div>
                        ) : assistantMsg.messageType === 'error' ? (
                          <div className="flex items-start gap-2 text-red-600">
                            <span className="text-red-500 mt-0.5 shrink-0">⚠</span>
                            <div className="flex-1 min-w-0">
                              <p className="font-semibold text-red-600 text-xs uppercase tracking-wide mb-1">
                                Error
                              </p>
                              <p className="text-red-700 text-sm break-words">
                                {assistantMsg.content}
                              </p>
                              <button
                                onClick={() => {
                                  const lastUser = [...messages]
                                    .reverse()
                                    .find(m => m.role === 'user');
                                  if (lastUser) {
                                    navigator.clipboard
                                      .writeText(lastUser.content)
                                      .catch(console.error);
                                    toast('Message copied — paste and try again.');
                                  }
                                }}
                                className="mt-3 inline-flex items-center gap-1.5 h-8 rounded-lg bg-red-50 border border-red-200 text-red-600 hover:bg-red-100 px-4 text-xs font-medium transition-colors"
                              >
                                <Copy className="size-3.5" />
                                Copy Message
                              </button>
                            </div>
                          </div>
                        ) : assistantMsg.messageType === 'itinerary' ? (
                          <div className="flex items-center gap-2 text-muted-foreground text-xs italic">
                            <span>✨</span>
                            <span>Your trip plan is ready below</span>
                          </div>
                        ) : (
                          <div>
                            <div className="prose prose-sm dark:prose-invert max-w-none break-words">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {DOMPurify.sanitize(assistantMsg.content)}
                              </ReactMarkdown>
                            </div>
                            {ttsAvailable && assistantMsg.content.trim() && (
                              <div className="mt-3 flex justify-end">
                                <button
                                  type="button"
                                  className="inline-flex items-center gap-1.5 rounded-md border border-input bg-background/60 px-2.5 py-1.5 text-xs text-muted-foreground hover:text-foreground hover:bg-background transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
                                      <Square className="size-3.5" />
                                      Stop
                                    </>
                                  ) : (
                                    <>
                                      <Volume2 className="size-3.5" />
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

                  {!assistantMsg && isLoading && isLastPair && <TypingIndicator />}
                </div>
              );
            })}

          {!sessionLoading && showDemoLoading && <DemoLoadingSkeleton />}

          {!sessionLoading && demoItinerary && (
            <div className="flex justify-start">
              <ItineraryDisplay itinerary={demoItinerary} />
            </div>
          )}

          {!sessionLoading && showGeneratedLoading && !generatedItinerary && (
            <DemoLoadingSkeleton />
          )}

          {!sessionLoading && generatedItinerary && (
            <div className="flex justify-start">
              <ItineraryDisplay itinerary={generatedItinerary} isGenerated />
            </div>
          )}
        </div>

        {/* Input bar section */}
        <div className="shrink-0 bg-background/80 backdrop-blur-sm border-t md:border-t-0 md:bg-transparent md:backdrop-blur-none">
          <TravelSettingsBar />
          <InputBar
            onItinerary={setGeneratedItinerary}
            onFinalizing={() => setShowGeneratedLoading(true)}
            onTripSaved={() => toast.success('Trip saved!')}
          />
        </div>

        <ConfirmDialog
          open={deleteSessionDialogId !== null}
          onOpenChange={open => !open && setDeleteSessionDialogId(null)}
          title="Delete this chat"
          description="Are you sure you want to delete this chat? This cannot be undone."
          confirmLabel="Delete"
          cancelLabel="Cancel"
          onConfirm={handleDeleteConfirm}
          destructive
        />

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
