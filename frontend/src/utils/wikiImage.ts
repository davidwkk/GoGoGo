export const BACKEND_ORIGIN = import.meta.env.VITE_API_URL
  ? new URL(import.meta.env.VITE_API_URL).origin
  : 'http://localhost:8000';

/**
 * Convert relative /images/ paths to full backend URLs.
 * Leaves absolute URLs (external images) unchanged.
 */
export function getBackendImageUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  if (url.startsWith('/images/')) {
    return `${BACKEND_ORIGIN}${url}`;
  }
  return url;
}

const VALID_IMAGE_TYPES = new Set([
  'image/jpeg',
  'image/png',
  'image/webp',
  'image/gif',
  'image/svg+xml',
]);

const ALLOWED_IMAGE_HOSTS = new Set(['upload.wikimedia.org']);

declare global {
  interface Window {
    __wikiQueueSystem: {
      queue: { url: string; resolve: (res: Response) => void; reject: (e: unknown) => void }[];
      isProcessing: boolean;
      cache: Map<string, string | Promise<string | null> | null>;
      process: () => Promise<void>;
      fetch: (url: string) => Promise<Response>;
    };
  }
}

const win = window as unknown as Window;

if (!win.__wikiQueueSystem) {
  win.__wikiQueueSystem = {
    queue: [],
    isProcessing: false,
    cache: new Map(),

    process: async () => {
      if (win.__wikiQueueSystem.isProcessing) return;
      win.__wikiQueueSystem.isProcessing = true;

      while (win.__wikiQueueSystem.queue.length > 0) {
        const { url, resolve, reject } = win.__wikiQueueSystem.queue[0];
        try {
          const res = await fetch(url);

          if (res.status === 429) {
            console.warn('Wiki 429 Rate Limit Hit. Pausing for 2 seconds then retrying...');
            await new Promise(r => setTimeout(r, 2000));
            continue;
          }

          win.__wikiQueueSystem.queue.shift();
          resolve(res);
        } catch (e) {
          win.__wikiQueueSystem.queue.shift();
          reject(e);
        }

        await new Promise(r => setTimeout(r, 500));
      }

      win.__wikiQueueSystem.isProcessing = false;
    },

    fetch: (url: string) => {
      return new Promise((resolve, reject) => {
        win.__wikiQueueSystem.queue.push({ url, resolve, reject });
        win.__wikiQueueSystem.process();
      });
    },
  };
}

async function validateImageMimeType(url: string): Promise<boolean> {
  try {
    const res = await fetch(url, { method: 'HEAD' });
    if (!res.ok) return false;
    const contentType = res.headers.get('Content-Type') ?? '';
    return VALID_IMAGE_TYPES.has(contentType);
  } catch {
    return false;
  }
}

export async function getWikiImage(searchQuery: string): Promise<string | null> {
  if (!searchQuery) return null;
  const query = searchQuery.trim().toLowerCase();

  const cached = win.__wikiQueueSystem.cache.get(query);
  if (cached !== undefined) {
    return typeof cached === 'string' ? cached : (cached ?? null);
  }

  const promise = (async () => {
    try {
      const res = await win.__wikiQueueSystem.fetch(
        `https://en.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch=${encodeURIComponent(searchQuery)}&gsrlimit=1&prop=pageimages&pithumbsize=800&format=json&origin=*`
      );

      if (res.ok) {
        const data = await res.json();
        const pages = data?.query?.pages;
        if (pages) {
          const pageId = Object.keys(pages)[0];
          const thumbnail = pages[pageId]?.thumbnail?.source;
          if (pageId !== '-1' && thumbnail) {
            try {
              const urlObj = new URL(thumbnail);
              if (ALLOWED_IMAGE_HOSTS.has(urlObj.host)) {
                const valid = await validateImageMimeType(thumbnail);
                if (valid) {
                  win.__wikiQueueSystem.cache.set(query, thumbnail);
                  return thumbnail;
                }
              }
            } catch {
              // Invalid URL, skip
            }
          }
        }
      }
    } catch (e) {
      console.error('Wiki fetch error', e);
    }

    win.__wikiQueueSystem.cache.set(query, null);
    return null;
  })();

  win.__wikiQueueSystem.cache.set(query, promise);
  return promise;
}

export function checkImageWorks(url: string): Promise<boolean> {
  return new Promise(resolve => {
    const img = new Image();
    const cleanup = () => {
      img.onload = null;
      img.onerror = null;
      img.src = '';
    };
    img.onload = () => {
      cleanup();
      resolve(true);
    };
    img.onerror = () => {
      cleanup();
      resolve(false);
    };
    img.src = url;
  });
}
