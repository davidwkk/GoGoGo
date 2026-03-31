// frontend/src/pages/TripPage.tsx
import { AlertCircle, Calendar, ChevronRight, Loader2, Map, MapPin } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ActivityCard } from '../components/trip/ActivityCard';
import { FlightCard } from '../components/trip/FlightCard';
import { tripService } from '../services/tripService';
import { DayPlan, Flight, TripDetail, TripSummary } from '../types/trip';

interface AuthError {
  userMessage?: string;
  message?: string;
}

// Component for Google Maps Embed (Task #24)
const MapEmbed = ({ url }: { url: string | null }) => {
  if (!url) return null;
  return (
    <section>
      <div className="w-full h-[300px] rounded-[2.5rem] overflow-hidden border border-slate-100 shadow-inner">
        <iframe
          title="Trip Map"
          width="100%"
          height="100%"
          style={{ border: 0 }}
          src={url}
          allowFullScreen
        ></iframe>
      </div>
    </section>
  );
};

function getStoredToken(): string | null {
  return localStorage.getItem('access_token');
}

export function TripPage() {
  const navigate = useNavigate();

  const [trips, setTrips] = useState<TripSummary[]>([]);
  const [selectedTrip, setSelectedTrip] = useState<TripDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchingDetail, setFetchingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Track auth state as React state so effects respond to changes correctly
  const [isLoggedIn, setIsLoggedIn] = useState(() => !!getStoredToken());
  const abortControllerRef = useRef<AbortController | null>(null);

  // --- DATA EXTRACTION HELPERS ---
  const hotel = selectedTrip?.itinerary?.hotels?.[0];

  const getNights = (inDate?: string, outDate?: string) => {
    if (!inDate || !outDate) return 1;
    const diff = new Date(outDate).getTime() - new Date(inDate).getTime();
    return Math.max(1, Math.ceil(diff / (1000 * 60 * 60 * 24)));
  };

  const nights = getNights(hotel?.check_in_date, hotel?.check_out_date);
  const minTotal = (hotel?.price_per_night_hkd?.min || 0) * nights;
  const maxTotal = (hotel?.price_per_night_hkd?.max || 0) * nights;

  // Sync auth state whenever localStorage changes (handles logout in other tabs/components)
  useEffect(() => {
    const handleStorage = () => setIsLoggedIn(!!getStoredToken());
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  // Fetch trips only when auth state becomes true (not on every render)
  useEffect(() => {
    if (!isLoggedIn) return;

    // Cancel any in-flight request from a previous auth state
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    abortControllerRef.current = new AbortController();

    setLoading(true);
    setError(null);
    tripService
      .listTrips()
      .then(data => setTrips(data || []))
      .catch(err => {
        // Ignore abort errors — they happen when user logs out mid-request
        if (
          err.name === 'CanceledError' ||
          (err instanceof Error && err.message.includes('cancel'))
        )
          return;
        const authErr = err as AuthError;
        if (authErr.userMessage) {
          setError(authErr.userMessage);
          // Redirect to login immediately
          navigate('/login');
        } else {
          setError('Unable to sync trips. Please check your connection.');
          console.error('Trip fetch error:', err);
        }
      })
      .finally(() => setLoading(false));

    return () => {
      abortControllerRef.current?.abort();
    };
  }, [isLoggedIn]);

  const handleSelectTrip = async (id: number) => {
    setFetchingDetail(true);
    try {
      const detail = await tripService.getTrip(id);
      setSelectedTrip(detail);
    } catch (err) {
      console.error('Failed to load trip details', err);
    } finally {
      setFetchingDetail(false);
    }
  };

  if (!isLoggedIn) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-white p-6 text-center">
        {error ? (
          <>
            <AlertCircle className="size-16 text-red-400 mb-4" />
            <h2 className="text-xl font-black text-slate-900 mb-2">Session Error</h2>
            <p className="text-sm text-red-500 mt-2 mb-6">{error}</p>
            <button
              onClick={() => navigate('/login')}
              className="h-12 rounded-2xl bg-black text-white px-10 text-sm font-bold hover:bg-slate-800 transition-all"
            >
              Go to Login
            </button>
          </>
        ) : (
          <>
            <Map className="size-16 text-slate-100 mb-4" />
            <h2 className="text-xl font-black text-slate-900">Sign in to view your trips</h2>
            <p className="text-sm text-slate-400 mt-2 mb-6">
              Create an account or sign in to save and manage your trip itineraries.
            </p>
            <button
              onClick={() => navigate('/login')}
              className="h-12 rounded-2xl bg-black text-white px-10 text-sm font-bold hover:bg-slate-800 transition-all"
            >
              Login to Account
            </button>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="flex h-screen bg-white text-slate-900">
      {/* SIDEBAR */}
      <div className="w-80 border-r flex flex-col bg-slate-50/50">
        <div className="p-6 border-b bg-white">
          <h1 className="text-xl font-black tracking-tight uppercase">My Trips</h1>
          <p className="text-[10px] text-slate-400 font-bold mt-1 uppercase">
            {loading ? 'Syncing...' : `${trips.length} saved plans`}
          </p>
          {error && (
            <div className="flex items-center gap-2 mt-2 text-red-500 text-xs">
              <AlertCircle className="size-3" />
              <span>{error}</span>
            </div>
          )}
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {loading && trips.length === 0 ? (
            <div className="flex justify-center py-20">
              <Loader2 className="animate-spin text-slate-200" />
            </div>
          ) : (
            trips.map(trip => (
              <button
                key={trip.id}
                onClick={() => handleSelectTrip(trip.id)}
                className={`w-full text-left p-4 rounded-2xl transition-all border ${
                  selectedTrip?.id === trip.id
                    ? 'bg-black text-white border-black shadow-xl scale-[1.02]'
                    : 'bg-white border-slate-100 hover:border-slate-300 text-slate-600 shadow-sm'
                }`}
              >
                <div className="flex justify-between items-start">
                  <p className="font-bold text-sm truncate pr-2">{trip.title}</p>
                  <ChevronRight
                    className={`size-3 mt-1 ${selectedTrip?.id === trip.id ? 'opacity-100' : 'opacity-10'}`}
                  />
                </div>
                <div className="flex items-center gap-1.5 mt-2 opacity-50">
                  <MapPin className="size-3" />
                  <span className="text-[10px] font-black uppercase tracking-tight">
                    {trip.destination}
                  </span>
                </div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 overflow-y-auto bg-white">
        {fetchingDetail ? (
          <div className="flex items-center justify-center h-full">
            <Loader2 className="animate-spin text-slate-200 size-12" />
          </div>
        ) : selectedTrip ? (
          <div className="max-w-3xl mx-auto p-12">
            <header className="mb-12">
              <div className="flex items-center gap-2 text-blue-600 mb-6 font-black text-[10px] uppercase tracking-[0.3em]">
                <Calendar className="size-4" /> Saved Itinerary
              </div>
              <h2 className="text-6xl font-black tracking-tighter mb-8 leading-none text-slate-900">
                {selectedTrip.title}
              </h2>
              <div className="p-8 bg-slate-50 rounded-[2rem] border border-slate-100 italic text-slate-500 text-xl shadow-inner">
                "{selectedTrip.itinerary.summary || 'No summary available'}"
              </div>
            </header>

            {/* Container for main sections to handle uniform spacing */}
            <div className="space-y-16">
              {/* 1. WEATHER SUMMARY (Moved up for better UX) */}
              {selectedTrip.itinerary.weather_summary && (
                <section>
                  <div className="p-6 bg-blue-50 rounded-[2rem] border border-blue-100 flex gap-4 items-center">
                    <div className="bg-white px-3 py-1 rounded-full shadow-sm font-black text-blue-600 text-[10px] uppercase tracking-widest whitespace-nowrap">
                      Travel Tip
                    </div>
                    <p className="text-xs text-blue-800 leading-relaxed font-medium italic">
                      {selectedTrip.itinerary.weather_summary}
                    </p>
                  </div>
                </section>
              )}

              {/* 2. FLIGHTS SECTION */}
              {selectedTrip.itinerary.flights && (
                <section>
                  <div className="flex items-center gap-4 mb-6">
                    <h3 className="text-xs font-black uppercase tracking-widest text-slate-400">
                      Flight Logistics
                    </h3>
                    <div className="h-px flex-1 bg-slate-100" />
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {selectedTrip.itinerary.flights.map((f: Flight, i: number) => (
                      <FlightCard key={i} flight={f} />
                    ))}
                  </div>
                </section>
              )}

              {/* 3. MAP EMBED (Task #24 Placeholder) */}
              {selectedTrip.itinerary.map_embed_url && (
                <MapEmbed url={selectedTrip.itinerary.map_embed_url} />
              )}

              {/* 4. ITINERARY DAYS */}
              <section>
                <div className="flex items-center gap-4 mb-10">
                  <h3 className="text-xs font-black uppercase tracking-widest text-slate-400">
                    Daily Schedule
                  </h3>
                  <div className="h-px flex-1 bg-slate-100" />
                </div>
                <div className="space-y-12">
                  {selectedTrip.itinerary.days?.map((day: DayPlan) => (
                    <div key={day.day_number}>
                      <div className="flex items-center gap-4 mb-8">
                        <div className="size-12 rounded-2xl bg-slate-900 text-white flex items-center justify-center font-black text-lg shadow-xl">
                          {day.day_number}
                        </div>
                        <div>
                          <p className="font-black text-xl text-slate-900">Day {day.day_number}</p>
                          <p className="text-xs text-slate-400 font-bold uppercase tracking-widest">
                            {day.date}
                          </p>
                        </div>
                      </div>

                      <div className="ml-2 border-l-2 border-slate-50 pl-2">
                        <ActivityCard activity={day.morning?.[0]} label="Morning" />
                        <ActivityCard activity={day.afternoon?.[0]} label="Afternoon" />
                        <ActivityCard activity={day.evening?.[0]} label="Evening" />
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              {/* 5. HOTEL SECTION */}
              {hotel && (
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
                      <button className="bg-white text-slate-900 px-10 py-4 rounded-2xl font-black text-sm hover:bg-blue-50 transition-all shadow-xl active:scale-95 uppercase tracking-widest">
                        Book Stay
                      </button>
                    </div>
                  </div>
                </section>
              )}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-center p-20 animate-in fade-in duration-500">
            <div className="relative mb-10">
              <div className="absolute inset-0 bg-blue-100 rounded-full blur-3xl opacity-20 scale-150" />
              <div className="relative bg-white border border-slate-100 rounded-full p-12 shadow-sm">
                <Map className="size-16 text-slate-100" />
              </div>
            </div>
            <h3 className="text-slate-900 font-black text-3xl tracking-tight">
              Your world, planned.
            </h3>
            <p className="text-slate-400 text-sm mt-3 max-w-xs leading-relaxed font-medium">
              Select an itinerary from your sidebar to unlock the full logistics of your next
              journey.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
