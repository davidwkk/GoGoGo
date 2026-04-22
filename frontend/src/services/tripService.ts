// frontend/src/services/tripService.ts
import { apiClient } from './api';
import type { TripDetail, TripSummary } from '../types/trip';

export { type TripSummary };

export const tripService = {
  /** List all trips for the current user */
  async listTrips(): Promise<TripSummary[]> {
    const { data } = await apiClient.get<TripSummary[]>('/trips');
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

  /** Create (save) a trip from a generated itinerary */
  async createTrip(itinerary: unknown): Promise<TripSummary> {
    const { data } = await apiClient.post<TripSummary>('/trips', { itinerary });
    return data;
  },

  /** Get the seeded demo trip (no auth required) */
  async getDemoTrip(): Promise<TripDetail> {
    const { data } = await apiClient.post<TripDetail>('/trips/demo');
    return data;
  },
};
