// frontend/src/services/tripService.ts
import { apiClient } from './api';
import type { TripDetail } from '../types/trip';

export interface TripSummary {
  id: number;
  title: string;
  destination: string;
  created_at: string;
}

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

  /** Get the seeded demo trip (no auth required) */
  async getDemoTrip(): Promise<TripDetail> {
    const { data } = await apiClient.post<TripDetail>('/trips/demo');
    return data;
  },
};
