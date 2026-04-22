import { Banknote, Bed, Calendar, MapPin, Plane, Sparkles, Ticket } from 'lucide-react';

import type { DayPlan, Flight, TripItinerary } from '@/types/trip';
import { AttractionCard } from '@/components/trip/AttractionCard';
import { FlightCard } from '@/components/trip/FlightCard';
import { HotelCard } from '@/components/trip/HotelCard';

export function ItineraryDisplay({
  itinerary,
  isGenerated,
}: {
  itinerary: TripItinerary;
  isGenerated?: boolean;
}) {
  const hotel = itinerary.hotels?.[0];
  const budget = itinerary.estimated_total_budget_hkd;

  const formatRange = (range?: { min: number; max: number }) => {
    if (!range) return 'N/A';
    if (range.min === range.max) return `HKD ${range.min.toLocaleString()}`;
    return `HKD ${range.min.toLocaleString()} - ${range.max.toLocaleString()}`;
  };

  const hasReturn = itinerary.flights?.some((f: Flight) => f.direction === 'return') ?? false;

  return (
    <div className="w-full max-w-3xl mx-auto bg-white rounded-3xl border border-slate-100 shadow-xl overflow-hidden">
      <div className="bg-linear-to-r from-slate-900 to-slate-800 p-6 md:p-8 text-white">
        <div className="flex items-center gap-2 text-blue-400 mb-4 font-black text-[10px] uppercase tracking-[0.3em]">
          <Sparkles className="size-4" /> {isGenerated ? 'Your Trip Plan' : 'Demo Trip Generated'}
        </div>
        <h2 className="text-3xl md:text-4xl font-black tracking-tight mb-4">
          {itinerary.destination}
        </h2>
        <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 text-sm text-slate-400">
          <span className="flex items-center gap-1">
            <Calendar className="size-3.5" />
            {itinerary.duration_days} days
          </span>
          <span className="flex items-center gap-1">
            <MapPin className="size-3.5" />
            {itinerary.flights?.length || 0} flights
          </span>
        </div>
      </div>

      <div className="p-6 md:p-8 space-y-8">
        {itinerary.summary && (
          <div className="bg-slate-50 rounded-2xl p-5 md:p-6 border border-slate-100 italic text-slate-600 text-base md:text-lg">
            "{itinerary.summary}"
          </div>
        )}

        {itinerary.weather_summary && (
          <div className="bg-blue-50 rounded-2xl p-4 md:p-5 border border-blue-100 flex flex-col sm:flex-row gap-3 sm:gap-4 sm:items-start">
            <div className="bg-blue-600 text-white px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest whitespace-nowrap w-fit">
              Travel Tip
            </div>
            <p className="text-xs text-blue-800 leading-relaxed">{itinerary.weather_summary}</p>
          </div>
        )}

        {budget && (
          <div>
            <div className="flex items-center gap-4 mb-6">
              <h3 className="text-xs font-black uppercase tracking-widest text-slate-400">
                Estimated Budget
              </h3>
              <div className="h-px flex-1 bg-slate-100" />
            </div>
            <div className="bg-white border border-slate-100 rounded-[2rem] p-6 md:p-8 shadow-sm">
              <div className="flex items-center justify-between gap-6 mb-6 md:mb-8 border-b border-slate-50 pb-6 md:pb-8">
                <div className="flex items-center gap-4">
                  <div className="size-10 md:size-12 rounded-2xl bg-emerald-50 text-emerald-600 flex items-center justify-center shadow-inner shrink-0">
                    <Banknote className="size-5 md:size-6" />
                  </div>
                  <div>
                    <p className="text-[10px] font-bold uppercase tracking-widest mb-1 text-slate-400">
                      Total Trip Estimate
                    </p>
                    <p className="text-2xl md:text-3xl font-black text-slate-900 tracking-tighter">
                      {formatRange(budget.total_hkd)}
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
                <div className="flex items-center gap-4">
                  <div className="p-3 bg-blue-50 text-blue-600 rounded-xl">
                    <Plane className="size-5" />
                  </div>
                  <div>
                    <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                      Flights
                    </p>
                    <p className="font-bold text-slate-700">{formatRange(budget.flights_hkd)}</p>
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
                    <p className="font-bold text-slate-700">{formatRange(budget.hotels_hkd)}</p>
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
                    <p className="font-bold text-slate-700">{formatRange(budget.activities_hkd)}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {itinerary.flights && itinerary.flights.length > 0 && (
          <div>
            <div className="flex items-center gap-4 mb-6">
              <h3 className="text-xs font-black uppercase tracking-widest text-slate-400">
                Flight Logistics
              </h3>
              <div className="h-px flex-1 bg-slate-100" />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
              {itinerary.flights.map((f: Flight, i: number) => (
                <FlightCard key={i} flight={f} tripType={hasReturn ? 'round_trip' : 'one_way'} />
              ))}
            </div>
          </div>
        )}

        <div>
          <div className="flex items-center gap-4 mb-8 md:mb-10">
            <h3 className="text-xs font-black uppercase tracking-widest text-slate-400">
              Daily Schedule
            </h3>
            <div className="h-px flex-1 bg-slate-100" />
          </div>
          <div className="space-y-10 md:space-y-12">
            {itinerary.days?.map((day: DayPlan) => (
              <div key={day.day_number}>
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6 md:mb-8">
                  <div className="flex items-center gap-4">
                    <div className="size-10 md:size-12 rounded-2xl bg-slate-900 text-white flex items-center justify-center font-black text-base md:text-lg shadow-xl shrink-0">
                      {day.day_number}
                    </div>
                    <div>
                      <h4 className="font-black text-lg md:text-xl text-slate-900 leading-tight md:leading-none">
                        Day {day.day_number}
                        {day.theme ? `: ${day.theme}` : ''}
                      </h4>
                      <p className="text-xs text-slate-400 font-bold uppercase tracking-widest mt-1 md:mt-1.5">
                        {day.date}
                      </p>
                    </div>
                  </div>
                  {day.estimated_daily_budget_hkd && (
                    <div className="flex items-center gap-2 px-3 py-1.5 bg-emerald-50 rounded-xl border border-emerald-100 shrink-0 self-start sm:self-auto">
                      <Banknote className="size-4 text-emerald-600" />
                      <span className="text-[10px] font-black text-emerald-700 uppercase tracking-widest">
                        {formatRange(day.estimated_daily_budget_hkd)}
                      </span>
                    </div>
                  )}
                </div>
                <div className="ml-2 sm:ml-4 border-l-2 border-slate-50 pl-4 sm:pl-6">
                  <AttractionCard activity={day.morning?.[0]} label="Morning" />
                  <AttractionCard activity={day.afternoon?.[0]} label="Afternoon" />
                  <AttractionCard activity={day.evening?.[0]} label="Evening" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {hotel && <HotelCard hotel={hotel} />}
      </div>
    </div>
  );
}
