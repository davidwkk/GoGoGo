import { Plane, ArrowRight, ExternalLink, Clock } from 'lucide-react';
import { Flight } from '../../types/trip';

export const FlightCard = ({
  flight,
  tripType = 'one_way',
}: {
  flight: Flight;
  tripType?: 'round_trip' | 'one_way';
}) => {
  // Dynamically calculate stops from the array
  const stopCount = flight.stops?.length || 0;
  const stopLabel = stopCount === 0 ? 'Direct' : `${stopCount} Stop${stopCount > 1 ? 's' : ''}`;

  const formatTime = (dateStr?: string | null) => {
    if (!dateStr) return null;
    try {
      const normalized = dateStr.endsWith('Z') ? dateStr.slice(0, -1) : dateStr;
      return new Date(normalized).toLocaleTimeString([], {
        hour: '2-digit',
        minute: '2-digit',
        timeZone: 'Asia/Hong_Kong',
      });
    } catch {
      return null;
    }
  };

  const formatDuration = (mins?: number | null) => {
    if (!mins) return null;
    const hrs = Math.floor(mins / 60);
    const m = mins % 60;
    return hrs > 0 ? `${hrs}h ${m}m` : `${m}m`;
  };

  const isReturn = flight.direction === 'return';
  const showPrice = !isReturn || tripType === 'one_way';

  const departureTime = formatTime(flight.departure_time);
  const arrivalTime = formatTime(flight.arrival_time);

  return (
    <div className="bg-white border border-slate-200 rounded-3xl p-6 shadow-sm hover:shadow-md transition-all group">
      {/* Header with Direction and Stop Badge */}
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-2 text-blue-600">
          <Plane className="size-4" />
          <span className="text-[10px] font-black uppercase tracking-[0.2em]">
            {flight.direction}
          </span>
        </div>
        <span
          className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase tracking-tighter ${
            stopCount === 0 ? 'bg-green-50 text-green-600' : 'bg-amber-50 text-amber-600'
          }`}
        >
          {stopLabel}
        </span>
      </div>

      {/* Route Display */}
      <div className="flex justify-between items-center mb-6">
        <div className="space-y-1">
          <p className="text-3xl font-black text-slate-900 tracking-tighter">
            {flight.departure_airport}
          </p>
          <p className="text-[11px] text-slate-400 font-bold uppercase">{departureTime || '---'}</p>
        </div>

        <div className="flex flex-col items-center gap-1 flex-1 px-4">
          <span className="text-[10px] font-bold text-slate-400 flex items-center gap-1">
            <Clock className="size-3" />
            {formatDuration(flight.duration_minutes) || '---'}
          </span>
          <ArrowRight className="text-slate-200 size-5" />
          <div className="h-px w-full bg-slate-100 relative">
            <div className="absolute inset-0 flex justify-center -top-1.5">
              <div className="size-3 bg-white border-2 border-slate-100 rounded-full" />
            </div>
          </div>
        </div>

        <div className="text-right space-y-1">
          <p className="text-3xl font-black text-slate-900 tracking-tighter">
            {flight.arrival_airport}
          </p>
          <p className="text-[11px] text-slate-400 font-bold uppercase">{arrivalTime || '---'}</p>
        </div>
      </div>

      {/* Footer Info */}
      <div className="pt-5 border-t border-slate-50 flex justify-between items-center">
        <div className="flex flex-col">
          <span className="text-xs font-bold text-slate-800">{flight.airline}</span>
          <span className="text-[10px] text-slate-400 font-medium tracking-tight">
            {flight.flight_number} {flight.airplane ? `• ${flight.airplane}` : ''}
          </span>
          {flight.travel_class && (
            <span className="text-[10px] text-blue-500 font-bold tracking-tight mt-0.5">
              {flight.travel_class}
            </span>
          )}
        </div>

        <div className="flex items-center gap-4">
          {showPrice ? (
            <div className="text-right">
              <p className="text-[9px] font-black text-slate-300 uppercase leading-none mb-1">
                {tripType === 'round_trip' ? 'Round Trip Total' : 'Total'}
              </p>
              <p className="text-sm font-black text-green-600">
                {flight.price_hkd ? `HKD ${flight.price_hkd.toLocaleString()}` : 'HKD ---'}
              </p>
            </div>
          ) : (
            <div className="text-right">
              <p className="text-[9px] font-black text-slate-300 uppercase leading-none mb-1">
                Included in
              </p>
              <p className="text-sm font-black text-slate-400">Round Trip</p>
            </div>
          )}

          {/* Conditional Booking Button */}
          {flight.booking_url && (
            <a
              href={flight.booking_url}
              target="_blank"
              rel="noopener noreferrer"
              className="bg-blue-600 hover:bg-blue-700 text-white p-2.5 rounded-xl transition-colors shadow-lg shadow-blue-100"
            >
              <ExternalLink className="size-4" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
};
