import { Clock, MapPin, Star, Lightbulb, Ticket, Image as ImageIcon } from 'lucide-react';
import { useState, useEffect } from 'react';
import type { Activity } from '@/types/trip';

const ActivityImage = ({
  imageUrl,
  name,
  category,
}: {
  imageUrl?: string | null;
  name: string;
  category?: string;
}) => {
  const [bgUrl, setBgUrl] = useState<string | null>(imageUrl || null);
  const [loading, setLoading] = useState(!imageUrl);

  useEffect(() => {
    // If backend provided an image, use it immediately
    if (imageUrl) {
      setBgUrl(imageUrl);
      return;
    }

    let isMounted = true;

    // The fallback image if Wikipedia fails
    const safeName = encodeURIComponent(name || 'travel');
    const fallbackUrl = `https://picsum.photos/seed/${safeName}/800/600`;

    const fetchWikiImage = async () => {
      try {
        // Switch to the Action API. It returns 200 OK even if the page is missing!
        // origin=* is required to prevent CORS errors
        const res = await fetch(
          `https://en.wikipedia.org/w/api.php?action=query&prop=pageimages&titles=${encodeURIComponent(name)}&pithumbsize=800&format=json&origin=*`
        );

        const data = await res.json();
        const pages = data.query?.pages;

        if (isMounted) {
          if (pages) {
            const pageId = Object.keys(pages)[0];
            // If pageId is '-1', the page doesn't exist.
            // If it exists but has no image, thumbnail will be undefined.
            if (pageId !== '-1' && pages[pageId].thumbnail?.source) {
              setBgUrl(pages[pageId].thumbnail.source);
              return; // Success!
            }
          }
          // If we reach here, no image was found, but NO 404 was thrown!
          setBgUrl(fallbackUrl);
        }
      } catch (e) {
        // Only actual network failures (like being offline) will trigger this now
        if (isMounted) setBgUrl(fallbackUrl);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchWikiImage();
    return () => {
      isMounted = false;
    };
  }, [name, imageUrl]);

  return (
    <div className="w-full h-48 relative bg-slate-100 overflow-hidden flex items-center justify-center">
      {bgUrl ? (
        <img
          src={bgUrl}
          alt={name}
          className="w-full h-full object-cover hover:scale-105 transition-transform duration-300"
        />
      ) : (
        <div className="text-slate-300 flex flex-col items-center gap-2">
          <ImageIcon className="size-8 opacity-50" />
          {loading && (
            <span className="text-[10px] font-bold uppercase tracking-widest">Searching...</span>
          )}
        </div>
      )}

      {category && (
        <div className="absolute top-3 left-3 bg-white/90 backdrop-blur-sm px-3 py-1 rounded-full shadow-sm">
          <span className="text-[10px] font-black uppercase tracking-widest text-blue-600">
            {category}
          </span>
        </div>
      )}
    </div>
  );
};

export const AttractionCard = ({
  activity,
  label,
}: {
  activity: Activity | Activity[];
  label: string;
}) => {
  if (!activity || (Array.isArray(activity) && activity.length === 0)) return null;
  const data = Array.isArray(activity) ? activity[0] : activity;

  const fee = data.admission_fee_hkd;
  const feeText = fee === 0 ? 'Free' : fee ? `HKD ${fee}` : null;

  return (
    <div className="relative pl-8 pb-8 last:pb-0 group">
      {/* Timeline Connector */}
      <div className="absolute left-[11px] top-2 bottom-0 w-px bg-slate-200 group-last:hidden" />
      <div className="absolute left-0 top-1 size-[23px] rounded-full border-4 border-white bg-blue-600 shadow-sm z-10" />

      <div className="bg-white border border-slate-100 rounded-2xl overflow-hidden shadow-sm hover:border-blue-200 transition-all hover:shadow-md flex flex-col">
        {/* Pass location into the image component for better Wiki searching */}
        <ActivityImage
          imageUrl={data.image_url || data.thumbnail_url}
          name={data.name || 'Activity'}
          category={data.category}
        />

        <div className="p-5 flex flex-col">
          <div className="flex justify-between items-start mb-2">
            <span className="text-[10px] font-black uppercase text-blue-500 tracking-tighter">
              {label}
            </span>
            <div className="flex items-center gap-3">
              {data.rating && (
                <div className="flex items-center gap-1 bg-yellow-50 px-2 py-1 rounded-lg">
                  <Star className="size-3 text-yellow-500 fill-yellow-500" />
                  <span className="text-xs font-bold text-yellow-700">{data.rating}</span>
                </div>
              )}
              {feeText && (
                <div className="flex items-center gap-1 text-slate-400">
                  <Ticket className="size-3" />
                  <span className="text-[10px] font-bold">{feeText}</span>
                </div>
              )}
              <div className="flex items-center gap-1 text-slate-400">
                <Clock className="size-3" />
                <span className="text-[10px] font-bold">
                  {data.estimated_duration_minutes || '60'}m
                </span>
              </div>
            </div>
          </div>

          <h4 className="font-bold text-slate-900 leading-tight">{data.name || 'Planned Stop'}</h4>

          <p className="text-[11px] text-slate-500 mt-1 line-clamp-2 leading-relaxed">
            {data.description || 'Enjoy your time exploring this location.'}
          </p>

          {data.tips && data.tips.length > 0 && (
            <div className="mt-3 space-y-1.5">
              {data.tips.map((tip: string, idx: number) => (
                <div
                  key={idx}
                  className="flex items-start gap-1.5 bg-amber-50 p-2 rounded-lg border border-amber-100"
                >
                  <Lightbulb className="size-3 text-amber-500 mt-0.5 shrink-0" />
                  <span className="text-[10px] font-medium text-amber-800 leading-tight">
                    {tip}
                  </span>
                </div>
              ))}
            </div>
          )}

          <div className="mt-3 flex items-center gap-1.5 text-slate-400">
            <MapPin className="size-3 text-blue-400" />
            <span className="text-[10px] font-medium truncate">
              {data.location || 'Location TBD'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
