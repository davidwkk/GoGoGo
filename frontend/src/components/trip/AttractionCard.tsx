import { Clock, MapPin, Star, Lightbulb, Ticket, Building2, Globe, Map } from 'lucide-react';
import { useState, useEffect } from 'react';
import type { Activity } from '@/types/trip';
import { ImageLightbox } from '../common/ImageLightbox';
import { MapEmbed } from './MapEmbed';
import { checkImageWorks, getWikiImage, getBackendImageUrl } from '@/utils/wikiImage';

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

    const loadBestImage = async () => {
      setLoading(true);

      // 1. Try provided backend image first
      // Transform relative /images/ paths to full backend URLs
      const backendImageUrl = getBackendImageUrl(imageUrl);
      if (backendImageUrl) {
        const works = await checkImageWorks(backendImageUrl);
        if (works && isMounted) {
          setImgSrc(backendImageUrl);
          setLoading(false);
          return;
        }
        // imageUrl exists but broken — don't fetch Wikipedia, use fallback
        if (isMounted) {
          const safeName = encodeURIComponent(name || 'travel');
          setImgSrc(`https://picsum.photos/seed/${safeName}/800/600`);
          setLoading(false);
          return;
        }
      }

      // 2. Fire BOTH Wikipedia searches in parallel (Queue protects us!)
      const cityQuery = location ? location.split(',')[0].trim() : '';

      const [attractionWiki, cityWiki] = await Promise.all([
        getWikiImage(name),
        cityQuery ? getWikiImage(cityQuery) : Promise.resolve(null),
      ]);

      // 3. Prioritize Attraction > City > Picsum
      if (isMounted) {
        if (attractionWiki) {
          setImgSrc(attractionWiki);
        } else if (cityWiki) {
          setImgSrc(cityWiki);
        } else {
          const safeName = encodeURIComponent(name || 'travel');
          setImgSrc(`https://picsum.photos/seed/${safeName}/800/600`);
        }
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
  const [showMap, setShowMap] = useState(false);

  if (!activity || (Array.isArray(activity) && activity.length === 0)) return null;
  const data = Array.isArray(activity) ? activity[0] : activity;

  const descriptionText = data.description || 'Enjoy your time exploring this location.';

  const fee = data.admission_fee_hkd;
  const feeText = fee === 0 ? 'Free' : fee ? `HKD ${fee}` : null;

  return (
    <div className="relative pl-8 pb-8 last:pb-0 group">
      <div className="absolute left-[11px] top-2 bottom-0 w-px bg-slate-200 group-last:hidden" />
      <div className="absolute left-0 top-1 size-[23px] rounded-full border-4 border-white bg-blue-600 shadow-sm z-10" />

      <div className="bg-white border border-slate-100 rounded-2xl overflow-hidden shadow-sm hover:border-blue-200 transition-all hover:shadow-md flex flex-col">
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

          <p className="mt-1 text-[11px] text-slate-500 leading-relaxed">{descriptionText}</p>

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

          <div className="mt-3 flex items-center justify-between">
            <button
              onClick={() => setShowMap(!showMap)}
              className="flex items-center gap-1.5 text-slate-400 hover:text-blue-600 transition-colors text-left group/loc"
              title="Click to view map"
            >
              <MapPin className="size-3 text-blue-400 shrink-0" />
              <span className="text-[10px] font-medium line-clamp-1 border-b border-dashed border-blue-200 group-hover/loc:border-blue-600 transition-colors">
                {data.location || 'Location TBD'}
              </span>
            </button>
            <div className="flex items-center gap-2">
              {data.wiki_url && (
                <a
                  href={data.wiki_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1 px-2 py-1 text-[10px] text-slate-500 hover:text-blue-600 transition-colors"
                >
                  <Globe className="size-3" />
                  Wiki
                </a>
              )}
              <button
                onClick={() => setShowMap(!showMap)}
                className={`flex items-center gap-1 px-2 py-1 text-[10px] transition-colors ${showMap ? 'text-blue-600 bg-blue-50 rounded-md' : 'text-slate-500 hover:text-blue-600'}`}
              >
                <Map className="size-3" />
                {showMap ? 'Hide Map' : 'Map'}
              </button>
            </div>
          </div>

          {/* Embedded Map */}
          {showMap && (
            <div className="mt-3 rounded-xl overflow-hidden border border-slate-200 h-48 bg-slate-50">
              <MapEmbed
                url={
                  data.map_url ||
                  `https://maps.google.com/maps?q=${encodeURIComponent(`${data.name} ${data.location || ''}`)}&output=embed`
                }
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
