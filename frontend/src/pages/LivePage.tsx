import { useCallback, useEffect, useMemo, useRef, useState, type SetStateAction } from 'react';
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

const LIVE_MODELS: { value: string; label: string }[] = [
  { value: 'gemini-3.1-flash-live-preview', label: '3.1 Flash Live (Default)' },
  {
    value: 'gemini-2.5-flash-native-audio-preview-12-2025',
    label: '2.5 Flash Native Audio (Backup)',
  },
];

function sortLiveSectionsForSidebar(list: LiveSectionPersisted[]): LiveSectionPersisted[] {
  return [...list].sort((a, b) => {
    const pa = a.pinned ? 1 : 0;
    const pb = b.pinned ? 1 : 0;
    if (pa !== pb) return pb - pa;
    return b.updatedAt - a.updatedAt;
  });
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
  } = useLiveSession({
    sectionKey: activeSectionId,
    transcripts: activeSection?.transcripts ?? [],
    setTranscripts: patchActiveTranscripts,
  });

  const live_model = useChatStore(s => s.live_model);
  const setLiveModel = useChatStore(s => s.setLiveModel);

  const handleModelChange = (val: string) => {
    setLiveModel(val);
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
        sections: prev.sections.map(s =>
          s.id === id ? { ...s, title: next, updatedAt: Date.now() } : s
        ),
      }));
      setEditingSectionId(null);
    },
    [titleDraft]
  );

  const togglePin = useCallback((id: string, pinned: boolean) => {
    setSnapshot(prev => ({
      ...prev,
      sections: prev.sections.map(s =>
        s.id === id ? { ...s, pinned: !pinned, updatedAt: Date.now() } : s
      ),
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
    () => status === 'connected' && text.trim().length > 0 && !isModelResponding,
    [status, text, isModelResponding]
  );

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
            <Select value={live_model} onValueChange={handleModelChange}>
              <SelectTrigger className="w-[240px]">
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
              Clear transcript
            </Button>
          </div>
        </header>

        <div className="flex-1 min-h-0 overflow-y-auto px-3 sm:px-6 py-4">
          {transcripts.length === 0 ? (
            <div className="text-sm text-muted-foreground">No messages yet.</div>
          ) : (
            <div className="space-y-6 max-w-4xl">
              {transcripts.map(t => (
                <div key={t.id} className="text-sm">
                  <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
                    {t.role}
                  </div>
                  {t.role === 'user' ? (
                    <div className="whitespace-pre-wrap break-words text-foreground">{t.text}</div>
                  ) : (
                    <div className="prose prose-sm dark:prose-invert max-w-none break-words">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {DOMPurify.sanitize(t.text)}
                      </ReactMarkdown>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="shrink-0 border-t bg-background/95 backdrop-blur-sm px-3 sm:px-6 py-3">
          <div className="flex flex-col gap-3">
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
                    : 'Connect to start…'
                }
                disabled={status !== 'connected'}
                onChange={e => setText(e.target.value)}
                onKeyDown={e => {
                  if (e.key !== 'Enter') return;
                  if (e.shiftKey) return; // Shift+Enter: manual newline
                  e.preventDefault(); // Enter: send
                  if (!canSend) return;
                  sendText(text.trim());
                  setText('');
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
            <div className="flex items-center gap-2 flex-wrap">
              <Button
                variant={isRecording ? 'destructive' : 'default'}
                disabled={status !== 'connected' || isModelResponding}
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
