// TravelSettingsBar — Collapsible bar above InputBar with travel preferences and trip parameters

import { Settings, ChevronDown } from 'lucide-react';

import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useChatStore } from '@/store';
import {
  type TravelStyle,
  type DietaryRestriction,
  type HotelTier,
  type GroupType,
  type TripPurpose,
} from '@/types/trip';

const TRAVEL_STYLES: { value: TravelStyle; label: string }[] = [
  { value: 'adventure', label: 'Adventure' },
  { value: 'relaxing', label: 'Relaxing' },
  { value: 'cultural', label: 'Cultural' },
  { value: 'foodie', label: 'Foodie' },
  { value: 'nature', label: 'Nature' },
  { value: 'shopping', label: 'Shopping' },
];

const DIETARY_RESTRICTIONS: { value: DietaryRestriction; label: string }[] = [
  { value: 'none', label: 'No Restriction' },
  { value: 'vegetarian', label: 'Vegetarian' },
  { value: 'vegan', label: 'Vegan' },
  { value: 'halal', label: 'Halal' },
  { value: 'kosher', label: 'Kosher' },
  { value: 'gluten_free', label: 'Gluten Free' },
];

const HOTEL_TIERS: { value: HotelTier; label: string }[] = [
  { value: 'budget', label: 'Budget' },
  { value: 'mid_range', label: 'Mid Range' },
  { value: 'luxury', label: 'Luxury' },
];

const GROUP_TYPES: { value: GroupType; label: string }[] = [
  { value: 'solo', label: 'Solo' },
  { value: 'couple', label: 'Couple' },
  { value: 'family', label: 'Family' },
  { value: 'friends', label: 'Friends' },
];

const TRIP_PURPOSES: { value: TripPurpose; label: string }[] = [
  { value: 'honeymoon', label: 'Honeymoon' },
  { value: 'graduation_trip', label: 'Graduation Trip' },
  { value: 'family_vacation', label: 'Family Vacation' },
  { value: 'solo_adventure', label: 'Solo Adventure' },
  { value: 'business_trip', label: 'Business Trip' },
  { value: 'first_trip', label: 'First Trip' },
  { value: 'anniversary', label: 'Anniversary' },
  { value: 'friends_getaway', label: 'Friends Getaway' },
];

const MAX_FLIGHT_STOPS = [
  { value: '0', label: 'Direct Only' },
  { value: '1', label: '1 Stop' },
  { value: '2', label: '2 Stops' },
];

export function TravelSettingsBar() {
  const travelSettings = useChatStore(s => s.travelSettings);
  const setTravelSettings = useChatStore(s => s.setTravelSettings);

  return (
    <details className="border-t bg-muted/20">
      <summary className="flex cursor-pointer select-none items-center gap-2 px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground list-none">
        <Settings className="size-4" />
        <span>Travel Settings</span>
        <ChevronDown className="size-4 ml-auto transition-transform duration-200 details[open]_:rotate-180" />
      </summary>

      <div className="grid grid-cols-1 gap-4 px-4 pb-4 md:grid-cols-2 lg:grid-cols-3">
        {/* Section: Trip Details */}
        <div className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Trip Details
          </h3>

          {/* Destination */}
          <div className="space-y-1.5">
            <Label htmlFor="destination">Destination</Label>
            <Input
              id="destination"
              placeholder="e.g. Tokyo, Japan"
              value={travelSettings.destination}
              onChange={e => setTravelSettings({ destination: e.target.value })}
            />
          </div>

          {/* Start Date */}
          <div className="space-y-1.5">
            <Label htmlFor="start_date">Start Date</Label>
            <Input
              id="start_date"
              type="date"
              value={travelSettings.start_date}
              onChange={e => setTravelSettings({ start_date: e.target.value })}
            />
          </div>

          {/* End Date */}
          <div className="space-y-1.5">
            <Label htmlFor="end_date">End Date</Label>
            <Input
              id="end_date"
              type="date"
              value={travelSettings.end_date}
              onChange={e => setTravelSettings({ end_date: e.target.value })}
            />
          </div>

          {/* Trip Purpose */}
          <div className="space-y-1.5">
            <Label htmlFor="purpose">Trip Purpose</Label>
            <Select
              value={travelSettings.purpose}
              onValueChange={value => setTravelSettings({ purpose: value as TripPurpose })}
            >
              <SelectTrigger id="purpose">
                <SelectValue placeholder="Select purpose" />
              </SelectTrigger>
              <SelectContent>
                {TRIP_PURPOSES.map(p => (
                  <SelectItem key={p.value} value={p.value}>
                    {p.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Group Type */}
          <div className="space-y-1.5">
            <Label htmlFor="group_type">Group Type</Label>
            <Select
              value={travelSettings.group_type}
              onValueChange={value => setTravelSettings({ group_type: value as GroupType })}
            >
              <SelectTrigger id="group_type">
                <SelectValue placeholder="Select group type" />
              </SelectTrigger>
              <SelectContent>
                {GROUP_TYPES.map(g => (
                  <SelectItem key={g.value} value={g.value}>
                    {g.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Group Size */}
          <div className="space-y-1.5">
            <Label htmlFor="group_size">Group Size</Label>
            <Input
              id="group_size"
              type="number"
              min={1}
              value={travelSettings.group_size}
              onChange={e => setTravelSettings({ group_size: parseInt(e.target.value) || 1 })}
            />
          </div>
        </div>

        {/* Section: User Preferences */}
        <div className="space-y-3">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Preferences
          </h3>

          {/* Travel Style */}
          <div className="space-y-1.5">
            <Label htmlFor="travel_style">Travel Style</Label>
            <Select
              value={travelSettings.travel_style}
              onValueChange={value => setTravelSettings({ travel_style: value as TravelStyle })}
            >
              <SelectTrigger id="travel_style">
                <SelectValue placeholder="Select travel style" />
              </SelectTrigger>
              <SelectContent>
                {TRAVEL_STYLES.map(s => (
                  <SelectItem key={s.value} value={s.value}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Dietary Restriction */}
          <div className="space-y-1.5">
            <Label htmlFor="dietary_restriction">Dietary Restriction</Label>
            <Select
              value={travelSettings.dietary_restriction}
              onValueChange={value =>
                setTravelSettings({
                  dietary_restriction: value as DietaryRestriction,
                })
              }
            >
              <SelectTrigger id="dietary_restriction">
                <SelectValue placeholder="Select dietary restriction" />
              </SelectTrigger>
              <SelectContent>
                {DIETARY_RESTRICTIONS.map(d => (
                  <SelectItem key={d.value} value={d.value}>
                    {d.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Hotel Tier */}
          <div className="space-y-1.5">
            <Label htmlFor="hotel_tier">Hotel Tier</Label>
            <Select
              value={travelSettings.hotel_tier}
              onValueChange={value => setTravelSettings({ hotel_tier: value as HotelTier })}
            >
              <SelectTrigger id="hotel_tier">
                <SelectValue placeholder="Select hotel tier" />
              </SelectTrigger>
              <SelectContent>
                {HOTEL_TIERS.map(h => (
                  <SelectItem key={h.value} value={h.value}>
                    {h.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Max Flight Stops */}
          <div className="space-y-1.5">
            <Label htmlFor="max_flight_stops">Max Flight Stops</Label>
            <Select
              value={String(travelSettings.max_flight_stops)}
              onValueChange={value => setTravelSettings({ max_flight_stops: parseInt(value) })}
            >
              <SelectTrigger id="max_flight_stops">
                <SelectValue placeholder="Select max stops" />
              </SelectTrigger>
              <SelectContent>
                {MAX_FLIGHT_STOPS.map(s => (
                  <SelectItem key={s.value} value={s.value}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Budget Min */}
          <div className="space-y-1.5">
            <Label htmlFor="budget_min">Budget Min (HKD)</Label>
            <Input
              id="budget_min"
              type="number"
              min={0}
              value={travelSettings.budget_min_hkd}
              onChange={e =>
                setTravelSettings({
                  budget_min_hkd: parseInt(e.target.value) || 0,
                })
              }
            />
          </div>

          {/* Budget Max */}
          <div className="space-y-1.5">
            <Label htmlFor="budget_max">Budget Max (HKD)</Label>
            <Input
              id="budget_max"
              type="number"
              min={0}
              value={travelSettings.budget_max_hkd}
              onChange={e =>
                setTravelSettings({
                  budget_max_hkd: parseInt(e.target.value) || 0,
                })
              }
            />
          </div>
        </div>
      </div>
    </details>
  );
}
