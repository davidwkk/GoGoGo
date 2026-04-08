import { Star, Building2 } from 'lucide-react';
import { MapEmbed } from './MapEmbed';
import { useState, useEffect } from 'react';
import { ImageLightbox } from '../common/ImageLightbox';
import { checkImageWorks, getWikiImage } from '@/utils/wikiImage';

export function HotelCard({ hotel }: { hotel: any }) {
  const [isLightboxOpen, setIsLightboxOpen] = useState(false);
  const [imgSrc, setImgSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!hotel) return;
    let isMounted = true;

    const loadBestImage = async () => {
      setLoading(true);

      // 1. Try backend image first
      if (hotel.image_url) {
        const works = await checkImageWorks(hotel.image_url);
        if (works && isMounted) {
          setImgSrc(hotel.image_url);
          setLoading(false);
          return;
        }
      }

      // 2. Fire BOTH Wikipedia searches in parallel (Queue protects us!)
      const locationString = hotel.location || hotel.city;
      const cityQuery = locationString ? locationString.split(',')[0].trim() : '';

      const [hotelWiki, cityWiki] = await Promise.all([
        getWikiImage(hotel.name),
        cityQuery ? getWikiImage(cityQuery) : Promise.resolve(null),
      ]);

      // 3. Pick the best result, or fallback to Picsum
      if (isMounted) {
        if (hotelWiki) {
          setImgSrc(hotelWiki);
        } else if (cityWiki) {
          setImgSrc(cityWiki);
        } else {
          const safeName = encodeURIComponent(hotel.name || 'hotel');
          setImgSrc(`https://picsum.photos/seed/${safeName}/800/400`);
        }
        setLoading(false);
      }
    };

    loadBestImage();

    return () => {
      isMounted = false;
    };
  }, [hotel]);

  if (!hotel) return null;

  const getNights = (inDate?: string, outDate?: string) => {
    if (!inDate || !outDate) return 1;
    const diff = new Date(outDate).getTime() - new Date(inDate).getTime();
    return Math.max(1, Math.ceil(diff / (1000 * 60 * 60 * 24)));
  };

  const nights = getNights(hotel.check_in_date, hotel.check_out_date);
  const minTotal = (hotel.price_per_night_hkd?.min || 0) * nights;
  const maxTotal = (hotel.price_per_night_hkd?.max || 0) * nights;

  return (
    <>
      <section className="bg-slate-900 rounded-[3rem] p-8 md:p-12 text-white shadow-2xl relative overflow-hidden group mb-10">
        <div className="absolute -right-10 -top-10 size-40 bg-blue-600/10 rounded-full blur-3xl group-hover:bg-blue-600/20 transition-colors" />

        <div className="relative z-10">
          <div
            className={`w-full h-48 md:h-64 mb-8 rounded-3xl overflow-hidden relative group/img ${imgSrc ? 'cursor-zoom-in' : ''} bg-slate-800 flex items-center justify-center`}
            onClick={() => imgSrc && setIsLightboxOpen(true)}
          >
            {loading && (
              <div className="absolute inset-0 flex flex-col items-center justify-center text-slate-500 bg-slate-800 z-10">
                <Building2 className="size-10 mb-2 animate-pulse" />
                <span className="text-[10px] font-bold tracking-widest uppercase animate-pulse">
                  Finding Photo...
                </span>
              </div>
            )}

            <div className="absolute inset-0 bg-black/20 group-hover/img:bg-transparent transition-colors z-10" />

            {imgSrc && (
              <img
                src={imgSrc}
                alt={hotel.name}
                className={`w-full h-full object-cover group-hover/img:scale-105 transition-transform duration-500 ${loading ? 'opacity-0' : 'opacity-100'}`}
              />
            )}
          </div>

          <div className="flex justify-between items-start mb-8">
            <span className="px-4 py-1 bg-blue-600 rounded-full text-[10px] font-black uppercase tracking-[0.2em] h-fit">
              Stay Details
            </span>
            <div className="text-right">
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">
                Nightly Rate
              </p>
              <p className="text-sm font-bold text-blue-400">
                HKD {hotel.price_per_night_hkd?.min?.toLocaleString()} -{' '}
                {hotel.price_per_night_hkd?.max?.toLocaleString()}
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1 mb-2 text-yellow-400">
            <Star className="size-4 fill-current" />
            <span className="text-sm font-bold">{hotel.rating || '4.5'}</span>
          </div>

          <h4 className="text-4xl font-black mb-3 tracking-tight">{hotel.name}</h4>

          <div className="flex flex-wrap gap-8 mb-10">
            <div>
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">
                Check-in
              </p>
              <p className="text-sm font-medium text-slate-200">{hotel.check_in_date}</p>
            </div>
            <div className="h-8 w-px bg-white/10 self-center" />
            <div>
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">
                Check-out
              </p>
              <p className="text-sm font-medium text-slate-200">{hotel.check_out_date}</p>
            </div>
            <div className="h-8 w-px bg-white/10 self-center" />
            <div>
              <p className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-1">
                Stay Duration
              </p>
              <p className="text-sm font-medium text-slate-200">
                {nights} {nights > 1 ? 'Nights' : 'Night'}
              </p>
            </div>
          </div>

          {hotel.embed_map_url && (
            <div className="mb-8 rounded-2xl overflow-hidden border border-white/10 h-80">
              <MapEmbed url={hotel.embed_map_url} />
            </div>
          )}

          <div className="flex justify-between items-end border-t border-white/10 pt-10">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-widest mb-2 text-blue-300">
                Total Stay Estimate
              </p>
              <p className="text-3xl font-black text-white tracking-tighter">
                HKD {minTotal.toLocaleString()}{' '}
                <span className="text-lg text-slate-500 font-medium lowercase">to</span>{' '}
                {maxTotal.toLocaleString()}
              </p>
            </div>
            <a
              href={hotel.booking_url || '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="bg-white text-slate-900 px-10 py-4 rounded-2xl font-black text-sm hover:bg-blue-50 transition-all shadow-xl active:scale-95 uppercase tracking-widest text-center inline-block"
            >
              Book Stay
            </a>
          </div>
        </div>
      </section>

      {isLightboxOpen && imgSrc && (
        <ImageLightbox
          imageUrl={imgSrc}
          altText={hotel.name}
          onClose={() => setIsLightboxOpen(false)}
        />
      )}
    </>
  );
}
