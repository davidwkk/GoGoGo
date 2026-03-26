// Trip service — API calls for trip CRUD operations

import { apiClient } from "@/services/api";

export interface TripSummary {
  id: number;
  title: string;
  destination: string;
  created_at: string;
}

export interface TripDetail extends TripSummary {
  itinerary: unknown; // TripItinerary
}

export const tripService = {
  /** List all trips for the current user */
  async getTrips(): Promise<TripSummary[]> {
    const { data } = await apiClient.get<TripSummary[]>("/trips");
    return data;
  },

  /** Get a single trip with full itinerary */
  async getTrip(tripId: number): Promise<TripDetail> {
    const { data } = await apiClient.get<TripDetail>(`/trips/${tripId}`);
    return data;
  },

  /** Delete a trip */
  async deleteTrip(tripId: number): Promise<void> {
    await apiClient.delete(`/trips/${tripId}`);
  },
};
