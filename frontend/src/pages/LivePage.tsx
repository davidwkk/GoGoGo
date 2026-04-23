import {
  Fragment,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type SetStateAction,
} from 'react';
import DOMPurify from 'dompurify';
import {
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Pencil,
  PlusCircle,
  Square,
  Star,
  Trash2,
  X,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { toast } from 'sonner';

import { useLiveSession, type LiveTranscriptItem } from '@/hooks/useLiveSession';
import {
  createDefaultLiveSnapshot,
  loadLiveSectionsSnapshot,
  saveLiveSectionsSnapshot,
  type LiveSectionPersisted,
  type LiveSectionsSnapshot,
} from '@/lib/liveSectionsStorage';
import { Button } from '@/components/ui/button';
import { ConfirmDialog } from '@/components/ui/confirm-dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useChatStore } from '@/store';
import { livePlanService } from '@/services/api';
import { tripService } from '@/services/tripService';
import { useAuthStore } from '@/store';
import { TripPlanningPreferenceFields } from '@/components/chat/TripPlanningPreferenceFields';
import { ItineraryDisplay } from '@/components/trip/ItineraryDisplay';
import type { TripItinerary } from '@/types/trip';

const LIVE_MODELS: { value: string; label: string }[] = [
  { value: 'gemini-3.1-flash-live-preview', label: '3.1 Flash Live (Default)' },
  {
    value: 'gemini-2.5-flash-native-audio-preview-12-2025',
    label: '2.5 Flash Native Audio (Backup)',
  },
];

const LIVE_VOICES: { value: string; label: string }[] = [
  { value: 'default', label: 'Default (model choice)' },
  { value: 'Zephyr', label: 'Zephyr' },
  { value: 'Puck', label: 'Puck' },
  { value: 'Charon', label: 'Charon' },
  { value: 'Fenrir', label: 'Fenrir' },
  { value: 'Kore', label: 'Kore' },
];

function sortLiveSectionsForSidebar(list: LiveSectionPersisted[]): LiveSectionPersisted[] {
  return [...list].sort((a, b) => {
    const pa = a.pinned ? 1 : 0;
    const pb = b.pinned ? 1 : 0;
    if (pa !== pb) return pb - pa;
    return b.updatedAt - a.updatedAt;
  });
}

function tryExtractJsonBlock(text: string): { jsonText: string; restText: string } | null {
  const s = text.trim();
  // Prefer fenced JSON blocks: ```json ... ```
  const fence = /```json\s*([\s\S]*?)\s*```/i.exec(s);
  if (fence?.[1]) {
    const jsonText = fence[1].trim();
    const restText = (s.slice(0, fence.index) + s.slice(fence.index + fence[0].length)).trim();
    return { jsonText, restText };
  }
  // Fallback: whole-message JSON
  if ((s.startsWith('{') && s.endsWith('}')) || (s.startsWith('[') && s.endsWith(']'))) {
    return { jsonText: s, restText: '' };
  }
  return null;
}

function StructuredPayload({ text }: { text: string }) {
  const extracted = useMemo(() => tryExtractJsonBlock(text), [text]);
  if (!extracted) return null;

  let pretty = extracted.jsonText;
  try {
    pretty = JSON.stringify(JSON.parse(extracted.jsonText), null, 2);
  } catch {
    // keep raw jsonText
  }

  return (
    <div className="mt-3 rounded-xl border bg-background/50 overflow-hidden">
      <div className="px-3 py-2 text-xs font-semibold text-muted-foreground border-b">
        Structured output
      </div>
      <pre className="p-3 text-xs overflow-x-auto whitespace-pre">{pretty}</pre>
      {extracted.restText && (
        <div className="px-3 pb-3 pt-0.5 text-xs text-muted-foreground">
          <div className="prose prose-sm dark:prose-invert max-w-none break-words">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {DOMPurify.sanitize(extracted.restText)}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}

function PlanningProcessPanel({
  steps,
  expanded,
  onToggleExpanded,
  busy,
}: {
  steps: string[];
  expanded: boolean;
  onToggleExpanded: () => void;
  busy: boolean;
}) {
  if (steps.length === 0 && !busy) return null;
  return (
    <div className="mt-2 rounded-xl border bg-muted/30 p-3">
      <button
        type="button"
        onClick={onToggleExpanded}
        className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors w-full text-left"
      >
        <span>💭 Thinking process</span>
        <span className={`transition-transform ${expanded ? 'rotate-90' : ''}`}>▶</span>
      </button>
      {expanded && (
        <div className="mt-2 space-y-1.5">
          {steps.map((s, i) => (
            <div key={i} className="text-xs text-muted-foreground break-words">
              {s}
            </div>
          ))}
          {busy && <div className="text-xs text-muted-foreground">Working…</div>}
        </div>
      )}
    </div>
  );
}

function looksLikeGeneratePlanIntent(s: string): boolean {
  const t = s.trim().toLowerCase();
  if (!t) return false;
  return (
    t === 'generate plan' ||
    t.includes('generate the plan') ||
    t.includes('now give me a travel plan') ||
    t.includes('give me a travel plan') ||
    t.includes('now give me a plan') ||
    t.includes('travel plan') ||
    t === '/plan'
  );
}

function isYesIntent(s: string): boolean {
  const t = s.trim().toLowerCase();
  if (!t) return false;
  // Accept common variants: "yes", "yes.", "yes please", "yes, save it", etc.
  return /^(yes|y)\b/.test(t);
}

function isNoIntent(s: string): boolean {
  const t = s.trim().toLowerCase();
  if (!t) return false;
  return /^(no|n)\b/.test(t);
}

function buildPlanPromptFromTranscripts(
  transcripts: LiveTranscriptItem[],
  userAsk: string
): string {
  const recent = transcripts.slice(-12);
  const lines = recent
    .filter(t => t.role === 'user' || t.role === 'model' || t.role === 'system')
    .map(t => `${t.role.toUpperCase()}: ${t.text}`.slice(0, 1200));
  return [
    'System: You are generating a trip plan based on the following context.',
    'System: DO NOT restate or recap this context. Use it silently and only output the trip plan content needed.',
    '',
    'Context (do not repeat):',
    ...lines,
    '',
    `User request: ${userAsk}`,
    'System: The user confirms: yes. Proceed with tool calls and finalize the plan.',
  ].join('\n');
}

export function LivePage() {
  const [snapshot, setSnapshot] = useState<LiveSectionsSnapshot>(() => {
    return loadLiveSectionsSnapshot() ?? createDefaultLiveSnapshot();
  });
  const { sections, activeSectionId } = snapshot;

  const [text, setText] = useState('');
  const [thinkingDots, setThinkingDots] = useState(1);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const [historyCollapsed, setHistoryCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [editingSectionId, setEditingSectionId] = useState<string | null>(null);
  const [titleDraft, setTitleDraft] = useState('');
  const [deleteSectionId, setDeleteSectionId] = useState<string | null>(null);

  const sortedSections = useMemo(() => sortLiveSectionsForSidebar(sections), [sections]);
  const activeSection = useMemo(
    () => sections.find(s => s.id === activeSectionId),
    [sections, activeSectionId]
  );

  const patchActiveTranscripts = useCallback((u: SetStateAction<LiveTranscriptItem[]>) => {
    setSnapshot(prev => ({
      ...prev,
      sections: prev.sections.map(sec =>
        sec.id === prev.activeSectionId
          ? {
              ...sec,
              transcripts: typeof u === 'function' ? u(sec.transcripts) : u,
              updatedAt: Date.now(),
            }
          : sec
      ),
    }));
  }, []);

  const patchActiveItinerary = useCallback((itinerary: LiveSectionPersisted['lastItinerary']) => {
    setSnapshot(prev => ({
      ...prev,
      sections: prev.sections.map(sec =>
        sec.id === prev.activeSectionId
          ? {
              ...sec,
              lastItinerary: itinerary ?? null,
              updatedAt: Date.now(),
            }
          : sec
      ),
    }));
  }, []);

  const patchActivePlanningSteps = useCallback((u: SetStateAction<string[]>) => {
    setSnapshot(prev => ({
      ...prev,
      sections: prev.sections.map(sec =>
        sec.id === prev.activeSectionId
          ? {
              ...sec,
              planningSteps: typeof u === 'function' ? u(sec.planningSteps ?? []) : u,
              updatedAt: Date.now(),
            }
          : sec
      ),
    }));
  }, []);

  const setPlanningExpanded = useCallback((expanded: boolean) => {
    setSnapshot(prev => ({
      ...prev,
      sections: prev.sections.map(sec =>
        sec.id === prev.activeSectionId
          ? { ...sec, planningExpanded: expanded, updatedAt: Date.now() }
          : sec
      ),
    }));
  }, []);

  const {
    status,
    transcripts,
    isRecording,
    isModelResponding,
    sendText,
    startRecording,
    stopRecording,
    stopResponse,
    clear,
    lastError,
  } = useLiveSession({
    sectionKey: activeSectionId,
    transcripts: activeSection?.transcripts ?? [],
    setTranscripts: patchActiveTranscripts,
  });

  const planningAnchorIndex = useMemo(() => {
    for (let i = transcripts.length - 1; i >= 0; i -= 1) {
      const tr = transcripts[i];
      if (tr.role === 'model' && /generating_trip_plan/i.test(tr.text)) return i;
    }
    return -1;
  }, [transcripts]);

  const token = useAuthStore(s => s.token);

  const [isPlanMode, setIsPlanMode] = useState(false);
  const [planBusy, setPlanBusy] = useState(false);
  const [pendingSavePrompt, setPendingSavePrompt] = useState(false);
  const planAbortRef = useRef<AbortController | null>(null);

  const showPlanningToolsPanel =
    planBusy || (activeSection?.planningSteps?.length ?? 0) > 0;

  const live_model = useChatStore(s => s.live_model);
  const setLiveModel = useChatStore(s => s.setLiveModel);
  const live_voice = useChatStore(s => s.live_voice);
  const setLiveVoice = useChatStore(s => s.setLiveVoice);
  const travelSettings = useChatStore(s => s.travelSettings);

  const handleModelChange = (val: string) => {
    setLiveModel(val);
  };

  const handleVoiceChange = (val: string) => {
    setLiveVoice(val);
  };

  useEffect(() => {
    if (lastError) toast.error(lastError);
  }, [lastError]);

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

  useEffect(() => {
    const t = window.setTimeout(() => {
      saveLiveSectionsSnapshot(snapshot);
    }, 400);
    return () => window.clearTimeout(t);
  }, [snapshot]);

  const resizeInput = useCallback(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${el.scrollHeight}px`;
  }, []);

  useEffect(() => {
    resizeInput();
  }, [text, resizeInput]);

  const newLiveChat = useCallback(() => {
    const n = snapshot.sections.length + 1;
    const id = crypto.randomUUID();
    const now = Date.now();
    const sec: LiveSectionPersisted = {
      id,
      title: `New Live Chat ${n}`,
      pinned: false,
      transcripts: [],
      createdAt: now,
      updatedAt: now,
    };
    setSnapshot(prev => ({
      sections: [...prev.sections, sec],
      activeSectionId: id,
    }));
    setMobileSidebarOpen(false);
  }, [snapshot.sections.length]);

  const selectSection = useCallback((id: string) => {
    setSnapshot(prev => ({ ...prev, activeSectionId: id }));
    setMobileSidebarOpen(false);
  }, []);

  const beginRename = useCallback((id: string, current: string) => {
    setEditingSectionId(id);
    setTitleDraft(current);
  }, []);

  const commitRename = useCallback(
    (id: string) => {
      const next = titleDraft.trim();
      if (!next) {
        setEditingSectionId(null);
        return;
      }
      setSnapshot(prev => ({
        ...prev,
        sections: prev.sections.map(s => (s.id === id ? { ...s, title: next } : s)),
      }));
      setEditingSectionId(null);
    },
    [titleDraft]
  );

  const togglePin = useCallback((id: string, pinned: boolean) => {
    setSnapshot(prev => ({
      ...prev,
      sections: prev.sections.map(s => {
        if (s.id !== id) return s;
        if (pinned) {
          return {
            ...s,
            pinned: false,
            updatedAt: s.pinnedOrderRestoreAt ?? s.updatedAt,
            pinnedOrderRestoreAt: undefined,
          };
        }
        return {
          ...s,
          pinned: true,
          pinnedOrderRestoreAt: s.updatedAt,
          updatedAt: Date.now(),
        };
      }),
    }));
  }, []);

  const requestDelete = useCallback((id: string) => {
    setDeleteSectionId(id);
  }, []);

  const confirmDelete = useCallback(() => {
    const id = deleteSectionId;
    if (!id) return;
    setDeleteSectionId(null);
    setSnapshot(prev => {
      const nextSections = prev.sections.filter(s => s.id !== id);
      if (nextSections.length === 0) {
        const fresh = createDefaultLiveSnapshot();
        return fresh;
      }
      let nextActive = prev.activeSectionId;
      if (id === prev.activeSectionId) {
        const sorted = sortLiveSectionsForSidebar(nextSections);
        nextActive = sorted[0].id;
      }
      return { sections: nextSections, activeSectionId: nextActive };
    });
  }, [deleteSectionId]);

  const canSend = useMemo(
    () => status === 'connected' && text.trim().length > 0 && !isModelResponding && !planBusy,
    [status, text, isModelResponding, planBusy]
  );

  const appendTranscript = useCallback(
    (role: LiveTranscriptItem['role'], text: string) => {
      patchActiveTranscripts(prev => [...prev, { id: crypto.randomUUID(), role, text }]);
    },
    [patchActiveTranscripts]
  );

  const runPlanTurn = useCallback(
    async (
      {
        displayText,
        sseText,
      }: {
        displayText: string;
        sseText: string;
      },
      { forceNew }: { forceNew: boolean }
    ) => {
      const t = displayText.trim();
      if (!t) return;

      if (travelSettings.budget_min_hkd > travelSettings.budget_max_hkd) {
        toast.error('Budget minimum must be less than or equal to maximum (HKD).');
        return;
      }

      // Stop WS response audio stream UI while we’re doing SSE planning
      stopResponse();

      // Optimistically add user message to transcript
      appendTranscript('user', t);

      // Reset planning steps UI for this run
      patchActivePlanningSteps([]);
      setPlanningExpanded(true);

      setPlanBusy(true);
      const abort = new AbortController();
      planAbortRef.current = abort;

      let fullText = '';
      let gotItinerary: unknown | null = null;
      let streamingMsgId: string | null = null;

      const req = {
        message: sseText,
        // Important: if logged in, DO NOT send a UUID session_id (backend rejects it).
        // Guests can send guest_uid to maintain continuity.
        session_id: (() => {
          if (token) return undefined;
          let guestUid = localStorage.getItem('guest_uid');
          if (!guestUid) {
            guestUid = crypto.randomUUID();
            localStorage.setItem('guest_uid', guestUid);
          }
          return guestUid;
        })(),
        force_new_session: forceNew || undefined,
        generate_plan: false,
        user_preferences: {
          travel_style: travelSettings.travel_style,
          dietary_restriction: travelSettings.dietary_restriction,
          hotel_tier: travelSettings.hotel_tier,
          budget_min_hkd: travelSettings.budget_min_hkd,
          budget_max_hkd: travelSettings.budget_max_hkd,
          max_flight_stops: travelSettings.max_flight_stops,
        },
      };

      try {
        for await (const chunk of livePlanService.streamPlan(req, abort.signal)) {
          if (typeof chunk === 'string') {
            if (chunk.startsWith('__ERROR__:')) {
              const err = chunk.slice('__ERROR__:'.length);
              appendTranscript('system', `Error: ${err}`);
              break;
            }
            if (chunk.startsWith('__ITINERARY__:')) {
              const raw = chunk.slice('__ITINERARY__:'.length);
              try {
                gotItinerary = JSON.parse(raw);
              } catch {
                gotItinerary = null;
              }
              continue;
            }
            if (chunk.startsWith('__FINALIZING__:')) {
              patchActivePlanningSteps(prev => [...prev, 'Finalizing trip plan…']);
              continue;
            }
            if (chunk.startsWith('__TOOL_CALL__:')) {
              patchActivePlanningSteps(prev => [
                ...prev,
                `Calling tool: ${chunk.slice('__TOOL_CALL__:'.length)}`,
              ]);
              continue;
            }
            if (chunk.startsWith('__TOOL_RESULT__:')) {
              patchActivePlanningSteps(prev => [
                ...prev,
                `Tool done: ${chunk.slice('__TOOL_RESULT__:'.length)}`,
              ]);
              continue;
            }
            if (chunk.startsWith('__RETRYINFO__:')) {
              patchActivePlanningSteps(prev => [
                ...prev,
                `Retrying… ${chunk.slice('__RETRYINFO__:'.length)}`,
              ]);
              continue;
            }
            if (chunk.startsWith('__MESSAGE_ID__:')) continue;
          }

          // Plain text chunk
          fullText += chunk;
          if (streamingMsgId === null) {
            streamingMsgId = crypto.randomUUID();
            patchActiveTranscripts(prev => [
              ...prev,
              { id: streamingMsgId!, role: 'model', text: fullText },
            ]);
          } else {
            patchActiveTranscripts(prev => {
              const last = prev.findIndex(x => x.id === streamingMsgId);
              if (last === -1) return prev;
              const next = [...prev];
              next[last] = { ...next[last], text: fullText };
              return next;
            });
          }
        }
      } catch (e) {
        const msg =
          e && typeof e === 'object' && 'detail' in e
            ? String((e as { detail?: string }).detail)
            : 'Plan stream failed';
        appendTranscript('system', `Error: ${msg}`);
      } finally {
        planAbortRef.current = null;
        setPlanBusy(false);
      }

      if (gotItinerary && typeof gotItinerary === 'object') {
        patchActiveItinerary(gotItinerary as Record<string, unknown>);
        appendTranscript(
          'model',
          'Plan generated. Do you need to save this plan? Reply "yes" to save.'
        );
        setPendingSavePrompt(true);
        setIsPlanMode(false); // exit plan mode after generation
      }
    },
    [
      appendTranscript,
      patchActiveItinerary,
      patchActivePlanningSteps,
      patchActiveTranscripts,
      setPlanningExpanded,
      stopResponse,
      token,
      travelSettings,
    ]
  );

  const handleSendFromInput = useCallback(async () => {
    const trimmed = text.trim();
    if (!trimmed || !canSend) return;
    setText('');

    // Save flow: user confirms saving
    if (pendingSavePrompt && isYesIntent(trimmed)) {
      const itinerary = activeSection?.lastItinerary;
      setPendingSavePrompt(false);
      if (!token) {
        appendTranscript('model', 'Please sign in to save trip plans to My Trips.');
        toast.error('Please sign in to save.');
        return;
      }
      if (!itinerary) {
        appendTranscript('system', 'Error: no itinerary found to save.');
        return;
      }
      try {
        appendTranscript('user', trimmed);
        await tripService.createTrip(itinerary);
        appendTranscript('model', 'Saved. You can view it in My Trips.');
        toast.success('Trip saved to My Trips');
      } catch (e) {
        appendTranscript(
          'system',
          `Error: ${(e as { detail?: string })?.detail ?? 'Failed to save trip'}`
        );
        toast.error('Failed to save trip');
      }
      return;
    }
    if (pendingSavePrompt && isNoIntent(trimmed)) {
      setPendingSavePrompt(false);
      appendTranscript('user', trimmed);
      appendTranscript(
        'model',
        'Okay — I won’t save it. Tell me what you want to change, or type “generate plan” to regenerate.'
      );
      return;
    }

    // Enter plan mode on intent and run a plan generation turn
    if (!isPlanMode && looksLikeGeneratePlanIntent(trimmed)) {
      setIsPlanMode(true);
      const prompt = buildPlanPromptFromTranscripts(transcripts, trimmed);
      await runPlanTurn({ displayText: trimmed, sseText: prompt }, { forceNew: true });
      return;
    }

    // If we’re currently in plan mode (follow-up answers), route to SSE planner.
    if (isPlanMode) {
      await runPlanTurn({ displayText: trimmed, sseText: trimmed }, { forceNew: false });
      return;
    }

    // Default: normal Gemini Live WS chat
    sendText(trimmed);
  }, [
    activeSection?.lastItinerary,
    appendTranscript,
    canSend,
    isPlanMode,
    pendingSavePrompt,
    runPlanTurn,
    sendText,
    text,
    token,
    transcripts,
  ]);

  return (
    <div className="flex h-screen bg-background overflow-hidden relative">
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 md:hidden"
          onClick={() => setMobileSidebarOpen(false)}
          aria-hidden
        />
      )}

      <aside
        className={`
          fixed inset-y-0 left-0 z-50 transform transition-transform duration-300 ease-in-out
          md:relative md:translate-x-0
          ${mobileSidebarOpen ? 'translate-x-0' : '-translate-x-full'}
          ${historyCollapsed ? 'md:w-0 md:border-r-0 md:overflow-hidden' : 'w-72 md:w-72 md:border-r'}
          bg-background flex flex-col overflow-hidden border-r shadow-2xl md:shadow-none
        `}
      >
        <div className="px-4 py-4 border-b flex-shrink-0 flex items-center justify-between">
          <div className="text-sm font-semibold">Live Chat History</div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => setMobileSidebarOpen(false)}
              className="md:hidden flex items-center justify-center h-8 w-8 rounded-xl bg-background text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
              aria-label="Close sidebar"
            >
              <X className="size-4" />
            </button>
            <button
              type="button"
              onClick={() => setHistoryCollapsed(true)}
              className="hidden md:flex items-center justify-center h-8 w-8 rounded-xl border border-border bg-background text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
              aria-label="Collapse live history"
              title="Collapse"
            >
              <PanelLeftClose className="size-4" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-2 space-y-1">
          <button
            type="button"
            onClick={newLiveChat}
            className="w-full flex items-center justify-center gap-1.5 h-9 rounded-xl border border-border bg-background px-3 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
          >
            <PlusCircle className="size-3" />
            New Live Chat
          </button>

          {sortedSections.map(s => {
            const active = activeSectionId === s.id;
            const isEditing = editingSectionId === s.id;
            return (
              <div
                key={s.id}
                className={`group rounded-xl border px-3 py-2 text-sm transition-colors cursor-pointer ${
                  active
                    ? 'bg-muted border-slate-300 shadow-sm'
                    : 'bg-background hover:bg-muted/40 border-slate-200'
                }`}
                onClick={() => {
                  if (isEditing || editingSectionId) return;
                  selectSection(s.id);
                }}
              >
                <div className="flex items-center gap-2">
                  {!isEditing && (
                    <button
                      type="button"
                      className={`shrink-0 rounded-md p-0.5 transition-colors hover:bg-muted/80 ${
                        s.pinned
                          ? 'text-amber-500'
                          : 'text-muted-foreground opacity-70 group-hover:opacity-100 md:opacity-0 md:group-hover:opacity-100'
                      }`}
                      onClick={e => {
                        e.stopPropagation();
                        togglePin(s.id, s.pinned);
                      }}
                      aria-label={s.pinned ? 'Unpin' : 'Pin to top'}
                      title={s.pinned ? 'Unpin' : 'Pin to top'}
                    >
                      <Star className={`size-3.5 ${s.pinned ? 'fill-amber-400' : ''}`} />
                    </button>
                  )}
                  {isEditing ? (
                    <input
                      className="h-7 flex-1 rounded-md border border-input bg-background px-2 text-sm focus:outline-none focus:ring-1 focus:ring-ring min-w-0"
                      value={titleDraft}
                      onChange={e => setTitleDraft(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') commitRename(s.id);
                        if (e.key === 'Escape') setEditingSectionId(null);
                      }}
                      autoFocus
                    />
                  ) : (
                    <span className="flex-1 text-left truncate min-w-0" title={s.title}>
                      {s.title}
                    </span>
                  )}
                  {!isEditing && (
                    <div className="flex items-center gap-1 md:opacity-0 md:group-hover:opacity-100 transition-opacity">
                      <button
                        type="button"
                        className="text-muted-foreground hover:text-foreground p-1"
                        onClick={e => {
                          e.stopPropagation();
                          beginRename(s.id, s.title);
                        }}
                        aria-label="Rename"
                      >
                        <Pencil className="size-3.5" />
                      </button>
                      <button
                        type="button"
                        className="text-muted-foreground hover:text-destructive p-1"
                        onClick={e => {
                          e.stopPropagation();
                          requestDelete(s.id);
                        }}
                        aria-label="Delete"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </aside>

      <main className="flex flex-col flex-1 min-w-0 min-h-0 bg-background relative">
        <header className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between shrink-0 px-3 sm:px-6 py-3 sm:py-4 border-b">
          <div className="flex items-start gap-2 min-w-0">
            <button
              type="button"
              onClick={() => setMobileSidebarOpen(true)}
              className="md:hidden flex items-center justify-center h-8 w-8 rounded-xl bg-background text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors shrink-0"
              aria-label="Open live history"
            >
              <Menu className="size-5" />
            </button>
            {historyCollapsed && (
              <button
                type="button"
                onClick={() => setHistoryCollapsed(false)}
                className="hidden md:flex items-center justify-center h-8 w-8 rounded-xl border border-border bg-background text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors shrink-0"
                aria-label="Expand live history"
                title="Expand"
              >
                <PanelLeftOpen className="size-4" />
              </button>
            )}
            {historyCollapsed && (
              <button
                type="button"
                onClick={newLiveChat}
                className="hidden md:flex items-center gap-1.5 h-8 rounded-xl border border-border bg-background px-3 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors shrink-0"
              >
                <PlusCircle className="size-3" />
                New Live Chat
              </button>
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <p className="text-sm font-semibold text-foreground truncate">
                  {activeSection?.title ?? 'Live'}
                </p>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <Button variant="ghost" onClick={clear} disabled={transcripts.length === 0}>
              Clear transcript
            </Button>
          </div>
        </header>

        <div className="flex-1 min-h-0 overflow-y-auto px-3 sm:px-6 py-4">
          {transcripts.length === 0 ? (
            <div className="text-sm text-muted-foreground">No messages yet.</div>
          ) : (
            <div className="space-y-6 max-w-4xl">
              {transcripts.map((t, idx) => {
                const showPlanningBelow =
                  showPlanningToolsPanel &&
                  (planningAnchorIndex >= 0
                    ? idx === planningAnchorIndex
                    : idx === transcripts.length - 1);
                return (
                  <Fragment key={t.id}>
                    <div className="text-sm">
                      <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                        {t.role}
                      </div>
                      {t.role === 'user' ? (
                        <div className="whitespace-pre-wrap break-words text-foreground">{t.text}</div>
                      ) : (
                        <div>
                          <div className="prose prose-sm dark:prose-invert max-w-none break-words">
                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                              {DOMPurify.sanitize(t.text)}
                            </ReactMarkdown>
                          </div>
                          {t.role === 'model' && <StructuredPayload text={t.text} />}
                        </div>
                      )}
                    </div>
                    {showPlanningBelow && (
                      <PlanningProcessPanel
                        steps={activeSection?.planningSteps ?? []}
                        expanded={activeSection?.planningExpanded ?? false}
                        onToggleExpanded={() =>
                          setPlanningExpanded(!(activeSection?.planningExpanded ?? false))
                        }
                        busy={planBusy}
                      />
                    )}
                  </Fragment>
                );
              })}
            </div>
          )}

          {/* Trip plan cards inside Live */}
          {activeSection?.lastItinerary && typeof activeSection.lastItinerary === 'object' && (
            <div className="mt-8">
              <ItineraryDisplay
                itinerary={activeSection.lastItinerary as TripItinerary}
                isGenerated
              />
            </div>
          )}
        </div>

        <div className="shrink-0 border-t bg-background/95 backdrop-blur-sm px-3 sm:px-6 py-3">
          <div className="flex flex-col gap-3">
            <div className="flex flex-col gap-2">
              <div className="text-xs font-medium text-muted-foreground">Preference</div>
              <div className="flex flex-wrap items-end gap-x-4 gap-y-3">
                <TripPlanningPreferenceFields idPrefix="live-" />
                <div className="flex items-center gap-2">
                  <div className="text-xs text-muted-foreground">Model</div>
                  <Select value={live_model} onValueChange={handleModelChange}>
                    <SelectTrigger className="w-[260px]">
                      <SelectValue placeholder="Select model" />
                    </SelectTrigger>
                    <SelectContent>
                      {LIVE_MODELS.map(m => (
                        <SelectItem key={m.value} value={m.value}>
                          {m.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-center gap-2">
                  <div className="text-xs text-muted-foreground">Voice</div>
                  <Select value={live_voice} onValueChange={handleVoiceChange}>
                    <SelectTrigger className="w-[220px]">
                      <SelectValue placeholder="Select voice" />
                    </SelectTrigger>
                    <SelectContent>
                      {LIVE_VOICES.map(v => (
                        <SelectItem key={v.value} value={v.value}>
                          {v.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <textarea
                ref={inputRef}
                value={text}
                rows={1}
                placeholder={
                  status === 'connected'
                    ? isModelResponding
                      ? 'Thinking… or press Stop to cancel'
                      : 'Type a message…'
                    : status === 'connecting'
                      ? 'Connecting…'
                      : 'Reconnecting…'
                }
                disabled={status !== 'connected'}
                onChange={e => setText(e.target.value)}
                onKeyDown={e => {
                  if (e.key !== 'Enter') return;
                  if (e.shiftKey) return; // Shift+Enter: manual newline
                  e.preventDefault(); // Enter: send
                  if (!canSend) return;
                  void handleSendFromInput();
                }}
                className="min-h-10 max-h-48 flex-1 w-full resize-none rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
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
                    void handleSendFromInput();
                  }}
                  disabled={!canSend}
                >
                  Send
                </Button>
              )}
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <Button
                variant={isRecording ? 'destructive' : 'default'}
                disabled={status !== 'connected' || isModelResponding || planBusy}
                onClick={() => {
                  if (status !== 'connected' || isModelResponding) return;
                  if (isRecording) stopRecording();
                  else void startRecording();
                }}
              >
                {isRecording ? 'Stop talking' : 'Push to talk'}
              </Button>
              <div className="text-xs text-muted-foreground">
                Status: <span className="font-medium">{status}</span>
                {planBusy && <span className="text-foreground">{' · Planning (tools)…'}</span>}
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
        </div>
      </main>

      <ConfirmDialog
        open={deleteSectionId !== null}
        onOpenChange={open => !open && setDeleteSectionId(null)}
        title="Delete this live chat"
        description="Are you sure you want to delete this live chat section? This cannot be undone."
        confirmLabel="Delete"
        cancelLabel="Cancel"
        onConfirm={confirmDelete}
        destructive
      />
    </div>
  );
}
