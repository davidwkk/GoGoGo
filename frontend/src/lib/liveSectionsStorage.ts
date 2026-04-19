import type { LiveTranscriptItem } from '@/hooks/useLiveSession';

export const LIVE_SECTIONS_STORAGE_KEY = 'gogogo-live-sections-v1';

export interface LiveSectionPersisted {
  id: string;
  title: string;
  pinned: boolean;
  /** `updatedAt` before pin; used to restore sidebar order after unpin */
  pinnedOrderRestoreAt?: number;
  transcripts: LiveTranscriptItem[];
  createdAt: number;
  updatedAt: number;
}

export interface LiveSectionsSnapshot {
  sections: LiveSectionPersisted[];
  activeSectionId: string;
}

export function loadLiveSectionsSnapshot(): LiveSectionsSnapshot | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(LIVE_SECTIONS_STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as Partial<LiveSectionsSnapshot>;
    if (!Array.isArray(data.sections) || data.sections.length === 0) return null;
    const sections = data.sections.map(s => {
      const rawPin = (s as { pinnedOrderRestoreAt?: unknown }).pinnedOrderRestoreAt;
      const pinnedOrderRestoreAt =
        rawPin != null && !Number.isNaN(Number(rawPin)) ? Number(rawPin) : undefined;
      return {
        id: String(s.id),
        title: String(s.title || 'Live'),
        pinned: Boolean(s.pinned),
        ...(pinnedOrderRestoreAt != null ? { pinnedOrderRestoreAt } : {}),
        transcripts: Array.isArray(s.transcripts) ? s.transcripts : [],
        createdAt: Number(s.createdAt) || Date.now(),
        updatedAt: Number(s.updatedAt) || Date.now(),
      };
    });
    let activeSectionId = String(data.activeSectionId || sections[0].id);
    if (!sections.some(s => s.id === activeSectionId)) {
      activeSectionId = sections[0].id;
    }
    return { sections, activeSectionId };
  } catch {
    return null;
  }
}

export function saveLiveSectionsSnapshot(snapshot: LiveSectionsSnapshot): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(LIVE_SECTIONS_STORAGE_KEY, JSON.stringify(snapshot));
  } catch {
    /* quota or private mode */
  }
}

export function createDefaultLiveSnapshot(): LiveSectionsSnapshot {
  const id = crypto.randomUUID();
  const now = Date.now();
  return {
    sections: [
      {
        id,
        title: 'New Live Chat 1',
        pinned: false,
        transcripts: [],
        createdAt: now,
        updatedAt: now,
      },
    ],
    activeSectionId: id,
  };
}
