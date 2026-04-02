// AttractionCard
import { Clock, MapPin, Star, Lightbulb, Ticket, Building2 } from 'lucide-react';
import { useState, useEffect } from 'react';
import type { Activity } from '@/types/trip';
import { ImageLightbox } from '../common/ImageLightbox';

const ActivityImage = ({
  imageUrl,
  name,
  location,
  category,
}: {
  imageUrl?: string | null;
  name: string;
  location?: string;
  category?: string;
}) => {
  const [imgSrc, setImgSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [isLightboxOpen, setIsLightboxOpen] = useState(false);

  useEffect(() => {
    let isMounted = true;

    // Helper to silently test if an image URL actually works (catches 403s)
    const checkImageWorks = (url: string): Promise<boolean> => {
      return new Promise(resolve => {
        const img = new Image();
        img.onload = () => resolve(true);
        img.onerror = () => resolve(false);
        img.src = url;
      });
    };

    // Robust Wikipedia search (fuzzy search)
    const getWikiImage = async (searchQuery: string): Promise<string | null> => {
      if (!searchQuery) return null;
      try {
        const res = await fetch(
          `https://en.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch=${encodeURIComponent(searchQuery)}&gsrlimit=1&prop=pageimages&pithumbsize=800&format=json&origin=*`
        );
        const data = await res.json();
        const pages = data.query?.pages;
        if (pages) {
          const pageId = Object.keys(pages)[0];
          if (pageId !== '-1' && pages[pageId].thumbnail?.source) {
            return pages[pageId].thumbnail.source;
          }
        }
      } catch (e) {
        console.error('Wiki fetch error', e);
      }
      return null;
    };

    const loadBestImage = async () => {
      setLoading(true);

      // 1. Try provided backend image first (and verify it works)
      if (imageUrl) {
        const works = await checkImageWorks(imageUrl);
        if (works && isMounted) {
          setImgSrc(imageUrl);
          setLoading(false);
          return;
        }
      }

      // 2. Try Wikipedia Fuzzy Search for the Attraction Name
      const attractionWiki = await getWikiImage(name);
      if (attractionWiki && isMounted) {
        setImgSrc(attractionWiki);
        setLoading(false);
        return;
      }

      // 3. Try Wikipedia Search for the Location/City as fallback
      if (location) {
        const cityQuery = location.split(',')[0].trim();
        const cityWiki = await getWikiImage(cityQuery);
        if (cityWiki && isMounted) {
          setImgSrc(cityWiki);
          setLoading(false);
          return;
        }
      }

      // 4. Absolute Last Resort: Picsum
      if (isMounted) {
        const safeName = encodeURIComponent(name || 'travel');
        setImgSrc(`https://picsum.photos/seed/${safeName}/800/600`);
        setLoading(false);
      }
    };

    loadBestImage();

    return () => {
      isMounted = false;
    };
  }, [name, imageUrl, location]);

  return (
    <>
      <div
        className={`w-full h-48 relative bg-slate-100 overflow-hidden flex items-center justify-center group/image ${imgSrc ? 'cursor-zoom-in' : ''}`}
        onClick={() => imgSrc && setIsLightboxOpen(true)}
      >
        {/* Loading Overlay */}
        {loading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-400 bg-slate-100 z-10">
            <Building2 className="size-8 mb-2 animate-pulse opacity-50" />
            <span className="text-[10px] font-bold uppercase tracking-widest animate-pulse">
              Finding Photo...
            </span>
          </div>
        )}

        <div className="absolute inset-0 bg-black/5 group-hover/image:bg-transparent transition-colors z-10" />

        {imgSrc && (
          <img
            src={imgSrc}
            alt={name}
            className={`w-full h-full object-cover hover:scale-105 transition-transform duration-300 ${loading ? 'opacity-0' : 'opacity-100'}`}
          />
        )}

        {category && (
          <div className="absolute top-3 left-3 bg-white/90 backdrop-blur-sm px-3 py-1 rounded-full shadow-sm z-20 pointer-events-none">
            <span className="text-[10px] font-black uppercase tracking-widest text-blue-600">
              {category}
            </span>
          </div>
        )}
      </div>

      {isLightboxOpen && imgSrc && (
        <ImageLightbox imageUrl={imgSrc} altText={name} onClose={() => setIsLightboxOpen(false)} />
      )}
    </>
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
        {/* Pass the correct props to the image component */}
        <ActivityImage
          imageUrl={data.image_url || data.thumbnail_url}
          name={data.name || 'Activity'}
          location={data.location}
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
