import { Star, Building2 } from 'lucide-react';
import { useState, useEffect } from 'react';
import { ImageLightbox } from '../common/ImageLightbox';

export function HotelCard({ hotel }: { hotel: any }) {
  const [isLightboxOpen, setIsLightboxOpen] = useState(false);

  // State for our bulletproof image loader
  const [imgSrc, setImgSrc] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!hotel) return;
    let isMounted = true;

    // Helper to silently test if an image URL actually works (catches Google 403s)
    const checkImageWorks = (url: string): Promise<boolean> => {
      return new Promise(resolve => {
        const img = new Image();
        img.onload = () => resolve(true);
        img.onerror = () => resolve(false);
        img.src = url;
      });
    };

    // NEW: Robust Wikipedia search instead of exact title match
    const getWikiImage = async (searchQuery: string): Promise<string | null> => {
      if (!searchQuery) return null;
      try {
        // Using generator=search makes it work like a real search bar, forgiving typos/missing exact titles
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

      // 1. Try backend image first
      if (hotel.image_url) {
        const works = await checkImageWorks(hotel.image_url);
        if (works && isMounted) {
          setImgSrc(hotel.image_url);
          setLoading(false);
          return;
        }
      }

      // 2. Try Wikipedia Search for Hotel Name (Fuzzy search)
      const hotelWiki = await getWikiImage(hotel.name);
      if (hotelWiki && isMounted) {
        setImgSrc(hotelWiki);
        setLoading(false);
        return;
      }

      // 3. Try Wikipedia Search for Location/City
      // (Checking both 'location' and 'city' in case a different key)
      const locationString = hotel.location || hotel.city;
      if (locationString) {
        // Grab just the city name if it's formatted like "Singapore, SG"
        const cityQuery = locationString.split(',')[0].trim();
        const cityWiki = await getWikiImage(cityQuery);
        if (cityWiki && isMounted) {
          setImgSrc(cityWiki);
          setLoading(false);
          return;
        }
      }

      // 4. Absolute Last Resort: Picsum
      if (isMounted) {
        const safeName = encodeURIComponent(hotel.name || 'hotel');
        setImgSrc(`https://picsum.photos/seed/${safeName}/800/400`);
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
          {/* Hotel Image Banner */}
          <div
            className={`w-full h-48 md:h-64 mb-8 rounded-3xl overflow-hidden relative group/img ${imgSrc ? 'cursor-zoom-in' : ''} bg-slate-800 flex items-center justify-center`}
            onClick={() => imgSrc && setIsLightboxOpen(true)}
          >
            {/* Loading State - Shows cleanly while background checks are happening */}
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
              href={hotel.booking_link || '#'}
              target="_blank"
              rel="noopener noreferrer"
              className="bg-white text-slate-900 px-10 py-4 rounded-2xl font-black text-sm hover:bg-blue-50 transition-all shadow-xl active:scale-95 uppercase tracking-widest text-center inline-block"
            >
              Book Stay
            </a>
          </div>
        </div>
      </section>

      {/* Render Lightbox if open */}
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
