// ============================================================
// Shared / Primitives
// ============================================================

export type ActivityCategory =
  | 'sightseeing'
  | 'food'
  | 'adventure'
  | 'culture'
  | 'shopping'
  | 'transport'
  | 'other';

export type CabinClass = 'economy' | 'premium_economy' | 'business' | 'first';

export interface PriceRange {
  min: number;
  max: number;
}

// ============================================================
// Activity
// ============================================================

export interface Activity {
  // --- Core (LLM-generated) ---
  name: string;
  description: string;
  location: string;
  estimated_duration_minutes: number;
  category: ActivityCategory; // LLM-inferred

  // --- Enriched via Tavily/SERP ---
  address?: string | null; // Full formatted address
  map_url?: string | null;
  opening_hours?: string | null; // e.g. "09:00–18:00, closed Mon"
  admission_fee_hkd?: number | null; // null = free
  rating?: number | null; // 0–5 from Google / TripAdvisor
  review_count?: number | null;
  booking_url?: string | null;
  tips?: string[] | null; // Extracted from reviews / Tavily snippets

  // --- Media (Tavily image search / SERP) ---
  image_url?: string | null;
  thumbnail_url?: string | null;
}

// ============================================================
// Day Plan
// ============================================================

export interface DayPlan {
  // --- Core ---
  day_number: number;
  date: string; // ISO 8601, e.g. "2025-06-01"
  morning: Activity[];
  afternoon: Activity[];
  evening: Activity[];

  // --- LLM-generated ---
  theme?: string | null; // e.g. "Cultural Immersion Day"
  notes?: string | null; // Daily tips or warnings

  // --- Budget ---
  estimated_daily_budget_hkd?: PriceRange | null;
}

// ============================================================
// Flight
// ============================================================

export interface FlightStop {
  airport_code: string;
  airport_name: string;
  arrival_time: string | null; // ISO 8601
  departure_time: string | null; // ISO 8601
}

export interface Flight {
  // --- Core (LLM-generated) ---
  direction: 'outbound' | 'return';
  airline: string;
  flight_number: string;
  departure_airport: string;
  arrival_airport: string;
  departure_time: string; // ISO 8601
  arrival_time: string; // ISO 8601
  stops: FlightStop[];

  // --- Enriched via SERP ---
  duration_minutes?: number | null;
  cabin_class?: CabinClass | null;
  price_hkd?: number | null; // Estimated fare
  booking_url?: string | null;
}

// ============================================================
// Hotel
// ============================================================

export interface Hotel {
  // --- Core (LLM-generated) ---
  name: string;
  check_in_date: string; // ISO 8601
  check_out_date: string; // ISO 8601
  price_per_night_hkd: PriceRange; // Replaced min/max with PriceRange

  // --- Enriched via SERP (Google Hotels, Booking.com) ---
  address?: string | null;
  star_rating?: number | null; // 1–5
  guest_rating?: number | null; // e.g. 8.4 out of 10
  booking_url?: string | null;
  image_url?: string | null;
  map_url?: string | null;
}

// ============================================================
// Trip Itinerary
// ============================================================

export interface BudgetBreakdown {
  flights_hkd: PriceRange;
  hotels_hkd: PriceRange;
  activities_hkd: PriceRange;
  total_hkd: PriceRange;
}

export interface TripItinerary {
  // --- Core (LLM-generated) ---
  destination: string;
  duration_days: number;
  summary: string;
  days: DayPlan[];
  hotels: Hotel[];
  flights: Flight[];

  // --- Weather (Tavily-enriched) ---
  weather_summary?: string | null;

  // --- Budget (computed from flights + hotels + activities) ---
  estimated_total_budget_hkd?: BudgetBreakdown | null;

  // --- Map ---
  map_embed_url?: string | null;
}

// ============================================================
// API Response Shapes
// ============================================================

// List view — lightweight, no itinerary payload
export interface TripSummary {
  id: number;
  title: string;
  destination: string;
  duration_days: number; // 🆕 useful for list card display
  created_at: string; // ISO 8601
  thumbnail_url?: string | null; // 🆕 first activity image or destination image
}

// Detail view — full payload
export interface TripDetail extends TripSummary {
  itinerary: TripItinerary;
}
