// frontend/src/components/trip/HotelCard.tsx
import { Star } from 'lucide-react';
// Import your actual type here, assuming it's HotelItem or similar
// import type { HotelItem } from '../../types/trip';

export function HotelCard({ hotel }: { hotel: any }) {
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
    <section className="bg-slate-900 rounded-[3rem] p-12 text-white shadow-2xl relative overflow-hidden group mb-10">
      <div className="absolute -right-10 -top-10 size-40 bg-blue-600/10 rounded-full blur-3xl group-hover:bg-blue-600/20 transition-colors" />

      <div className="relative z-10">
        <div className="flex justify-between items-start mb-8">
          <span className="px-4 py-1 bg-blue-600 rounded-full text-[10px] font-black uppercase tracking-[0.2em]">
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

        {/* Added Rating Display */}
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
          {/* Booking Link Button */}
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
  );
}
