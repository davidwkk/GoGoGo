// frontend/src/pages/TripPage.tsx
import React, { useEffect, useState, useCallback } from 'react';
import { Map, Calendar, MapPin, ChevronRight, AlertCircle, Loader2 } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { tripService } from '../services/tripService';
import { TripSummary, TripDetail } from '../types/trip';

export function TripPage() {
  const navigate = useNavigate();
  const token = localStorage.getItem('token') || localStorage.getItem('access_token');
  const isLoggedIn = !!token;
  
  const [trips, setTrips] = useState<TripSummary[]>([]);
  const [selectedTrip, setSelectedTrip] = useState<TripDetail | null>(null);
  const [loading, setLoading] = useState(isLoggedIn);
  const [fetchingDetail, setFetchingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadTrips = useCallback(async () => {
    if (!isLoggedIn) return;
    setLoading(true);
    setError(null);
    try {
      // Now matches the name in tripService.ts
      const data = await tripService.listTrips();
      setTrips(data || []);
    } catch (err) {
      setError("Unable to sync trips. Please check your connection.");
      console.error("Trip fetch error:", err);
    } finally {
      setLoading(false);
    }
  }, [isLoggedIn]);

  useEffect(() => {
    loadTrips();
  }, [loadTrips]);

  const handleSelectTrip = async (id: number) => {
    setFetchingDetail(true);
    try {
      const detail = await tripService.getTrip(id);
      setSelectedTrip(detail);
    } catch (err) {
      console.error("Failed to load trip details", err);
    } finally {
      setFetchingDetail(false);
    }
  };

  if (!isLoggedIn) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-white p-6">
        <Map className="size-12 text-slate-200 mb-4" />
        <h2 className="text-lg font-bold">Sign in to view your trips</h2>
        <button
          onClick={() => navigate('/login')}
          className="mt-4 h-10 rounded-xl bg-black text-white px-8 text-sm font-medium hover:bg-slate-800 transition-all"
        >
          Login
        </button>
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
            {loading ? 'Loading...' : `${trips.length} saved plans`}
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-2">
          {loading && trips.length === 0 ? (
            <div className="flex justify-center py-10"><Loader2 className="animate-spin text-slate-300" /></div>
          ) : trips.length === 0 ? (
            <div className="text-center py-12 px-6 text-slate-400 text-xs">No trips found. Go to chat to create one!</div>
          ) : (
            trips.map((trip) => (
              <button
                key={trip.id}
                onClick={() => handleSelectTrip(trip.id)}
                className={`w-full text-left p-4 rounded-2xl transition-all border ${
                  selectedTrip?.id === trip.id 
                    ? 'bg-black text-white border-black shadow-xl' 
                    : 'bg-white border-slate-100 hover:border-slate-300 text-slate-600'
                }`}
              >
                <div className="flex justify-between items-start">
                  <p className="font-bold text-sm truncate">{trip.title}</p>
                  <ChevronRight className={`size-3 mt-1 ${selectedTrip?.id === trip.id ? 'opacity-100' : 'opacity-10'}`} />
                </div>
                <div className="flex items-center gap-1 mt-2 opacity-50">
                  <MapPin className="size-3" />
                  <span className="text-[10px] font-bold uppercase">{trip.destination}</span>
                </div>
              </button>
            ))
          )}
        </div>
        
        {error && (
          <div className="m-4 p-3 bg-red-50 text-red-600 rounded-lg text-[10px] font-bold uppercase flex items-center gap-2 border border-red-100">
            <AlertCircle className="size-4" /> {error}
          </div>
        )}
      </div>

      {/* CONTENT AREA */}
      <div className="flex-1 overflow-y-auto bg-white">
        {selectedTrip ? (
          <div className="max-w-3xl mx-auto p-12">
            <header className="mb-12">
              <div className="flex items-center gap-2 text-blue-600 mb-4 font-black text-[10px] uppercase tracking-widest">
                <Calendar className="size-4" /> Confirmed Plan
              </div>
              <h2 className="text-5xl font-black tracking-tighter mb-6">{selectedTrip.title}</h2>
              <div className="p-8 bg-slate-50 rounded-[2rem] border border-slate-100 italic text-slate-500 text-lg">
                "{selectedTrip.itinerary.summary || 'No summary available'}"
              </div>
            </header>

            <div className="bg-slate-900 p-8 rounded-[2rem] shadow-2xl overflow-hidden">
               <p className="text-[10px] font-mono text-slate-500 mb-4 uppercase tracking-widest">Payload Response</p>
               <pre className="text-[11px] font-mono text-blue-300 overflow-x-auto leading-relaxed">
                 {JSON.stringify(selectedTrip.itinerary, null, 2)}
               </pre>
            </div>
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-slate-300">
            <Map className="size-16 opacity-10 mb-4" />
            <p className="text-sm font-medium">Select a trip to view the itinerary</p>
          </div>
        )}
      </div>
    </div>
  );
}