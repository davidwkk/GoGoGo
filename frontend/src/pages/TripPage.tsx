// frontend/src/pages/TripPage.tsx
import {
  AlertCircle,
  Calendar,
  Map,
  MapPin,
  Banknote,
  Plane,
  Bed,
  Ticket,
  Trash2,
} from 'lucide-react';
import { toast } from 'sonner';
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AttractionCard } from '../components/trip/AttractionCard';
import { FlightCard } from '../components/trip/FlightCard';
import { tripService } from '../services/tripService';
import { DayPlan, Flight, TripDetail, TripSummary } from '../types/trip';
import { HotelCard } from '../components/trip/HotelCard';
import { ConfirmDialog } from '../components/ui/confirm-dialog';

// --- SKELETON COMPONENTS (defined after imports per ES module rules) ---

function SidebarTripSkeleton() {
  return (
    <div className="w-full p-4 rounded-2xl border bg-white border-slate-100 mb-2">
      <div className="flex justify-between items-start">
        <div className="h-4 bg-slate-200 rounded w-2/3 animate-pulse" />
        <div className="size-4 bg-slate-100 rounded animate-pulse" />
      </div>
      <div className="flex items-center gap-1.5 mt-4">
        <div className="size-3 bg-slate-200 rounded-full animate-pulse" />
        <div className="h-2.5 bg-slate-200 rounded w-1/3 animate-pulse" />
      </div>
    </div>
  );
}

function TripDetailSkeleton() {
  return (
    <div className="max-w-3xl mx-auto p-12 w-full animate-in fade-in duration-300">
      {/* Header Skeleton */}
      <div className="h-3 w-32 bg-blue-100 rounded mb-6 animate-pulse" />
      <div className="h-14 w-3/4 bg-slate-200 rounded-lg mb-8 animate-pulse" />
      <div className="h-24 w-full bg-slate-50 rounded-[2rem] mb-12 animate-pulse border border-slate-100" />

      <div className="space-y-16">
        {/* Budget Skeleton */}
        <div className="h-40 w-full bg-slate-50 rounded-[2rem] animate-pulse border border-slate-100" />

        {/* Flights Skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="h-32 w-full bg-slate-50 rounded-[2rem] animate-pulse border border-slate-100" />
          <div className="h-32 w-full bg-slate-50 rounded-[2rem] animate-pulse border border-slate-100" />
        </div>

        {/* Map Skeleton */}
        <div className="h-64 w-full bg-slate-100 rounded-3xl animate-pulse" />

        {/* Days Skeleton */}
        <div className="space-y-10">
          {[1, 2].map(i => (
            <div key={i}>
              <div className="flex items-center gap-4 mb-6">
                <div className="size-12 rounded-2xl bg-slate-200 animate-pulse shrink-0" />
                <div className="h-6 w-32 bg-slate-100 rounded animate-pulse" />
              </div>
              <div className="ml-6 border-l-2 border-slate-50 pl-6 space-y-4">
                <div className="h-24 w-full bg-slate-50 rounded-2xl animate-pulse" />
                <div className="h-24 w-full bg-slate-50 rounded-2xl animate-pulse" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

interface AuthError {
  userMessage?: string;
  message?: string;
}

function getStoredToken(): string | null {
  return localStorage.getItem('access_token');
}

export function TripPage() {
  const navigate = useNavigate();

  const [trips, setTrips] = useState<TripSummary[]>([]);
  const [selectedTrip, setSelectedTrip] = useState<TripDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [fetchingDetail, setFetchingDetail] = useState(false);
  const [deletingTripId, setDeletingTripId] = useState<number | null>(null);
  const [deleteConfirmTripId, setDeleteConfirmTripId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Track auth state as React state so effects respond to changes correctly
  const [isLoggedIn, setIsLoggedIn] = useState(() => !!getStoredToken());
  const abortControllerRef = useRef<AbortController | null>(null);

  // --- DATA EXTRACTION HELPERS ---
  const hotel = selectedTrip?.itinerary?.hotels?.[0];
  const budget = selectedTrip?.itinerary?.estimated_total_budget_hkd;

  const formatRange = (range?: { min: number; max: number }) => {
    if (!range) return 'N/A';
    if (range.min === range.max) return `HKD ${range.min.toLocaleString()}`;
    return `HKD ${range.min.toLocaleString()} - ${range.max.toLocaleString()}`;
  };

  // Sync auth state whenever localStorage changes (handles logout in other tabs/components)
  useEffect(() => {
    const handleStorage = () => setIsLoggedIn(!!getStoredToken());
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  // --- DAVID'S FIX: Extract fetch logic to a reusable function ---
  const fetchTrips = () => {
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
        // Only handle if authErr has a user-facing message — auth errors are already
        // handled by the api interceptor's toast + redirect, so skip them here
        if (authErr?.userMessage) {
          setError(authErr.userMessage);
          // Redirect to login immediately
          toast.dismiss();
          navigate('/login');
        } else {
          setError('Unable to sync trips. Please check your connection.');
          console.error('Trip fetch error:', err);
        }
      })
      .finally(() => setLoading(false));
  };

  // Fetch trips only when auth state becomes true (not on every render)
  useEffect(() => {
    fetchTrips();

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

  const handleDeleteTrip = async (tripId: number) => {
    setDeleteConfirmTripId(tripId);
  };

  const confirmDeleteTrip = async (tripId: number) => {
    setDeletingTripId(tripId);
    try {
      await tripService.deleteTrip(tripId);
      setTrips(prev => prev.filter(t => t.id !== tripId));
      if (selectedTrip?.id === tripId) {
        setSelectedTrip(null);
      }
      toast.success('Trip deleted');
    } catch (err) {
      console.error('Failed to delete trip', err);
      toast.error('Failed to delete this trip. Please try again.');
    } finally {
      setDeletingTripId(null);
    }
  };

  if (!isLoggedIn) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-3 text-center">
        {error ? (
          <>
            <AlertCircle className="size-8 text-red-400" />
            <div>
              <p className="text-sm font-medium text-destructive">Connection Error</p>
              <p className="text-xs text-muted-foreground mt-0.5">{error}</p>
            </div>
            <div className="flex gap-2 mt-2">
              <button
                onClick={fetchTrips} // --- DAVID'S FIX: Call the fetch function instead of reload ---
                className="h-8 rounded-xl bg-slate-100 text-slate-900 px-4 text-sm font-medium hover:bg-slate-200 transition-colors"
              >
                Try Again
              </button>
              <button
                onClick={() => {
                  toast.dismiss();
                  navigate('/login');
                }}
                className="h-8 rounded-xl bg-black text-white px-4 text-sm font-medium hover:opacity-80 transition-opacity"
              >
                Go to Login
              </button>
            </div>
          </>
        ) : (
          <>
            <Map className="size-8 text-muted-foreground" />
            <div>
              <p className="text-sm font-medium">Sign in to view your trips</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Create an account or sign in to save and manage your trip itineraries.
              </p>
            </div>
            <button
              onClick={() => {
                toast.dismiss();
                navigate('/login');
              }}
              className="h-8 rounded-xl bg-black text-white px-4 text-sm font-medium hover:opacity-80 transition-opacity"
            >
              Sign in
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
            <>
              <SidebarTripSkeleton />
              <SidebarTripSkeleton />
              <SidebarTripSkeleton />
            </>
          ) : (
            trips.map(trip => (
              <div
                key={trip.id}
                className={`w-full p-4 rounded-2xl transition-all border ${
                  selectedTrip?.id === trip.id
                    ? 'bg-black text-white border-black shadow-xl scale-[1.02]'
                    : 'bg-white border-slate-100 hover:border-slate-300 text-slate-600 shadow-sm'
                }`}
              >
                <div className="flex items-start gap-2">
                  <button
                    onClick={() => handleSelectTrip(trip.id)}
                    className="flex-1 min-w-0 text-left"
                  >
                    <div className="flex justify-between items-start">
                      <p className="font-bold text-sm truncate pr-2">{trip.title}</p>
                    </div>
                    <div className="flex items-center gap-1.5 mt-2 opacity-50">
                      <MapPin className="size-3" />
                      <span className="text-[10px] font-black uppercase tracking-tight truncate">
                        {trip.destination}
                      </span>
                    </div>
                  </button>

                  <button
                    type="button"
                    className={`mt-0.5 shrink-0 rounded-lg p-2 transition-colors ${
                      selectedTrip?.id === trip.id
                        ? 'text-white/70 hover:text-white hover:bg-white/10'
                        : 'text-slate-400 hover:text-red-600 hover:bg-red-50'
                    } disabled:opacity-50`}
                    aria-label="Delete trip"
                    title="Delete"
                    disabled={deletingTripId === trip.id}
                    onClick={e => {
                      e.stopPropagation();
                      handleDeleteTrip(trip.id);
                    }}
                  >
                    <Trash2 className="size-4" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* MAIN CONTENT AREA */}
      <div className="flex-1 overflow-y-auto bg-white">
        {fetchingDetail ? (
          <TripDetailSkeleton />
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

              {/* 1.5 OVERALL BUDGET SUMMARY */}
              {budget && (
                <section>
                  <div className="flex items-center gap-4 mb-6">
                    <h3 className="text-xs font-black uppercase tracking-widest text-slate-400">
                      Estimated Budget
                    </h3>
                    <div className="h-px flex-1 bg-slate-100" />
                  </div>

                  <div className="bg-white border border-slate-100 rounded-[2rem] p-8 shadow-sm">
                    {/* Total */}
                    <div className="flex items-center justify-between gap-6 mb-8 border-b border-slate-50 pb-8">
                      <div className="flex items-center gap-4">
                        <div className="size-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center shadow-inner">
                          <Banknote className="size-6" />
                        </div>
                        <div>
                          <p className="text-[10px] font-bold uppercase tracking-widest mb-1 text-slate-400">
                            Total Trip Estimate
                          </p>
                          <p className="text-3xl font-black text-slate-900 tracking-tighter">
                            {formatRange(budget.total_hkd)}
                          </p>
                        </div>
                      </div>
                    </div>

                    {/* Breakdown Grid */}
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                      <div className="flex items-center gap-4">
                        <div className="p-3 bg-blue-50 text-blue-600 rounded-xl">
                          <Plane className="size-5" />
                        </div>
                        <div>
                          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                            Flights
                          </p>
                          <p className="font-bold text-slate-700">
                            {formatRange(budget.flights_hkd)}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="p-3 bg-purple-50 text-purple-600 rounded-xl">
                          <Bed className="size-5" />
                        </div>
                        <div>
                          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                            Hotels
                          </p>
                          <p className="font-bold text-slate-700">
                            {formatRange(budget.hotels_hkd)}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="p-3 bg-orange-50 text-orange-600 rounded-xl">
                          <Ticket className="size-5" />
                        </div>
                        <div>
                          <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                            Activities
                          </p>
                          <p className="font-bold text-slate-700">
                            {formatRange(budget.activities_hkd)}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                </section>
              )}

              {/* 2. FLIGHT SECTION */}
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

              {/* 3. ITINERARY DAYS */}
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
                      {/* --- UPDATED DAY HEADER --- */}
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8">
                        <div className="flex items-center gap-4">
                          <div className="size-12 rounded-2xl bg-slate-900 text-white flex items-center justify-center font-black text-lg shadow-xl shrink-0">
                            {day.day_number}
                          </div>
                          <div>
                            <h4 className="font-black text-xl text-slate-900 leading-none">
                              Day {day.day_number}
                              {day.theme ? `: ${day.theme}` : ''}
                            </h4>
                            <p className="text-xs text-slate-400 font-bold uppercase tracking-widest mt-1.5">
                              {day.date}
                            </p>
                          </div>
                        </div>

                        {/* Daily Budget Badge */}
                        {day.estimated_daily_budget_hkd && (
                          <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-50 rounded-xl border border-emerald-100 shrink-0 self-start sm:self-auto">
                            <Banknote className="size-4 text-emerald-600" />
                            <span className="text-[10px] font-black text-emerald-700 uppercase tracking-widest">
                              {formatRange(day.estimated_daily_budget_hkd)}
                            </span>
                          </div>
                        )}
                      </div>
                      {/* --- END UPDATED DAY HEADER --- */}

                      <div className="ml-2 border-l-2 border-slate-50 pl-2">
                        <AttractionCard activity={day.morning?.[0]} label="Morning" />
                        <AttractionCard activity={day.afternoon?.[0]} label="Afternoon" />
                        <AttractionCard activity={day.evening?.[0]} label="Evening" />
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              {/* 5. HOTEL SECTION */}
              {hotel && <HotelCard hotel={hotel} />}
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
            <div className="flex items-center justify-center rounded-full bg-muted size-12">
              <Map className="size-5 text-muted-foreground" />
            </div>
            <div>
              <p className="text-sm font-medium">Your world, planned.</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Select an itinerary from your sidebar to unlock the full logistics of your next
                journey.
              </p>
            </div>
          </div>
        )}
      </div>

      <ConfirmDialog
        open={deleteConfirmTripId !== null}
        onOpenChange={open => {
          if (!open) setDeleteConfirmTripId(null);
        }}
        title="Delete this trip plan?"
        description="This cannot be undone. All flights, hotels, and activities in this itinerary will be permanently removed."
        confirmLabel="Delete"
        cancelLabel="Keep"
        destructive
        onConfirm={() => {
          if (deleteConfirmTripId !== null) {
            confirmDeleteTrip(deleteConfirmTripId);
          }
        }}
      />
    </div>
  );
}
