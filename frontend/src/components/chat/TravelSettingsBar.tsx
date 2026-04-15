// TravelSettingsBar — Collapsible bar above InputBar with travel preferences

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
import { type TravelStyle, type DietaryRestriction, type HotelTier } from '@/types/trip';

const TRAVEL_STYLES: { value: TravelStyle; label: string }[] = [
  { value: 'adventure', label: 'Adventure' },
  { value: 'relaxing', label: 'Relaxing' },
  { value: 'cultural', label: 'Cultural' },
  { value: 'foodie', label: 'Foodie' },
  { value: 'nature', label: 'Nature' },
  { value: 'shopping', label: 'Shopping' },
  { value: 'no_special_style', label: 'No Special Style' },
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

const MAX_FLIGHT_STOPS = [
  { value: '0', label: 'Direct Only' },
  { value: '1', label: '1 Stop' },
  { value: '2', label: '2 Stops' },
];

const LLM_MODELS: { value: string; label: string }[] = [
  { value: 'gemini-3.1-flash-lite-preview', label: '3.1 Flash Lite (Fast)' },
  { value: 'gemini-3-flash-preview', label: '3 Flash (Smart)' },
  { value: 'gemini-2.5-flash-lite', label: '2.5 Flash Lite (Backup)' },
  { value: 'gemini-2.5-flash', label: '2.5 Flash (Backup)' },
];

export function TravelSettingsBar() {
  const travelSettings = useChatStore(s => s.travelSettings);
  const setTravelSettings = useChatStore(s => s.setTravelSettings);
  const llm_model = useChatStore(s => s.llm_model);
  const setLlmModel = useChatStore(s => s.setLlmModel);

  console.log('[TravelSettingsBar] llm_model from store:', llm_model);

  return (
    <details className="border-t bg-muted/20">
      <summary className="flex cursor-pointer select-none items-center gap-2 px-4 py-2 text-sm font-medium text-muted-foreground hover:text-foreground list-none">
        <Settings className="size-4" />
        <span>Preferences</span>
        <ChevronDown className="size-4 ml-auto transition-transform duration-200 details[open]_:rotate-180" />
      </summary>

      <div className="flex flex-wrap items-center gap-4 px-4 pb-4">
        {/* Travel Style */}
        <div className="space-y-1">
          <Label htmlFor="travel_style" className="text-xs">
            Style
          </Label>
          <Select
            value={travelSettings.travel_style}
            onValueChange={value => setTravelSettings({ travel_style: value as TravelStyle })}
          >
            <SelectTrigger id="travel_style" className="w-[140px]">
              <SelectValue />
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
        <div className="space-y-1">
          <Label htmlFor="dietary_restriction" className="text-xs">
            Diet
          </Label>
          <Select
            value={travelSettings.dietary_restriction}
            onValueChange={value =>
              setTravelSettings({
                dietary_restriction: value as DietaryRestriction,
              })
            }
          >
            <SelectTrigger id="dietary_restriction" className="w-[140px]">
              <SelectValue />
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
        <div className="space-y-1">
          <Label htmlFor="hotel_tier" className="text-xs">
            Hotel
          </Label>
          <Select
            value={travelSettings.hotel_tier}
            onValueChange={value => setTravelSettings({ hotel_tier: value as HotelTier })}
          >
            <SelectTrigger id="hotel_tier" className="w-[120px]">
              <SelectValue />
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
        <div className="space-y-1">
          <Label htmlFor="max_flight_stops" className="text-xs">
            Flights
          </Label>
          <Select
            value={String(travelSettings.max_flight_stops)}
            onValueChange={value => setTravelSettings({ max_flight_stops: parseInt(value) })}
          >
            <SelectTrigger id="max_flight_stops" className="w-[120px]">
              <SelectValue />
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

        {/* Budget */}
        <div className="space-y-1">
          <Label htmlFor="budget_min" className="text-xs">
            Budget (HKD)
          </Label>
          <div className="flex items-center gap-1">
            <Input
              id="budget_min"
              type="number"
              min={0}
              placeholder="Min"
              className="w-[80px]"
              value={travelSettings.budget_min_hkd}
              onChange={e =>
                setTravelSettings({
                  budget_min_hkd: parseInt(e.target.value) || 0,
                })
              }
            />
            <span className="text-muted-foreground">-</span>
            <Input
              id="budget_max"
              type="number"
              min={0}
              placeholder="Max"
              className="w-[80px]"
              value={travelSettings.budget_max_hkd}
              onChange={e =>
                setTravelSettings({
                  budget_max_hkd: parseInt(e.target.value) || 0,
                })
              }
            />
          </div>
        </div>

        {/* LLM Model */}
        <div className="space-y-1">
          <Label htmlFor="llm_model" className="text-xs">
            Model
          </Label>
          <Select
            value={llm_model}
            onValueChange={val => {
              console.log('[TravelSettingsBar] model selected:', val);
              setLlmModel(val);
            }}
          >
            <SelectTrigger id="llm_model" className="w-[180px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {LLM_MODELS.map(m => (
                <SelectItem key={m.value} value={m.value}>
                  {m.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
    </details>
  );
}
