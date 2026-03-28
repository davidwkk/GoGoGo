export interface Activity {
  name: string;
  description: string;
  location: string;
  map_url: string | null;
  estimated_duration_minutes: number;
}

export interface DayPlan {
  day_number: number;
  date: string;
  morning: Activity[];
  afternoon: Activity[];
  evening: Activity[];
}

export interface FlightStop {
  airport_code: string;
  airport_name: string;
  arrival_time: string | null;
  departure_time: string | null;
}

export interface Flight {
  direction: 'outbound' | 'return';
  airline: string;
  flight_number: string;
  departure_airport: string;
  arrival_airport: string;
  departure_time: string;
  arrival_time: string;
  stops: FlightStop[];
  booking_url: string | null;
}

export interface Hotel {
  name: string;
  check_in_date: string;
  check_out_date: string;
  price_per_night_min_hkd: number;
  price_per_night_max_hkd: number;
}

export interface TripItinerary {
  destination: string;
  duration_days: number;
  summary: string;
  days: DayPlan[];
  hotels: Hotel[];
  flights: Flight[];
  weather_summary: string;
  map_embed_url?: string;
}

// What the List View returns
export interface TripSummary {
  id: number;
  title: string;
  destination: string;
  created_at: string;
}

// What the Detail View returns
export interface TripDetail extends TripSummary {
  itinerary: TripItinerary;
}
