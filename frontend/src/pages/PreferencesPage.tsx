// PreferencesPage — Travel preferences for guests

import { useEffect, useState } from 'react';
import { Settings } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Separator } from '@/components/ui/separator';
import { Button } from '@/components/ui/button';
import { guestPreferences, GuestPreferences, DEFAULT_GUEST_PREFERENCES } from '@/services/api';

const TRAVEL_STYLES = [
  { value: 'adventure', label: 'Adventure' },
  { value: 'relaxing', label: 'Relaxing' },
  { value: 'cultural', label: 'Cultural' },
  { value: 'foodie', label: 'Foodie' },
  { value: 'nature', label: 'Nature' },
  { value: 'shopping', label: 'Shopping' },
];

const DIETARY_OPTIONS = [
  { value: 'none', label: 'None' },
  { value: 'vegetarian', label: 'Vegetarian' },
  { value: 'vegan', label: 'Vegan' },
  { value: 'halal', label: 'Halal' },
  { value: 'kosher', label: 'Kosher' },
  { value: 'gluten_free', label: 'Gluten-Free' },
];

const HOTEL_TIERS = [
  { value: 'budget', label: 'Budget' },
  { value: 'mid_range', label: 'Mid-Range' },
  { value: 'luxury', label: 'Luxury' },
];

const MAX_STOPS_OPTIONS = [
  { value: '0', label: 'Direct only' },
  { value: '1', label: 'Up to 1 stop' },
  { value: '2', label: 'Up to 2 stops' },
];

export function PreferencesPage() {
  const [prefs, setPrefs] = useState<GuestPreferences>(() => guestPreferences.get());
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setPrefs(guestPreferences.get());
  }, []);

  const handleSave = () => {
    guestPreferences.set(prefs);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  const handleReset = () => {
    setPrefs(DEFAULT_GUEST_PREFERENCES);
    guestPreferences.set(DEFAULT_GUEST_PREFERENCES);
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <div className="max-w-md mx-auto py-8 px-4 space-y-6">
      <div className="flex items-center gap-3">
        <Settings className="size-6 text-muted-foreground" />
        <h1 className="text-2xl font-semibold">Travel Preferences</h1>
      </div>

      <p className="text-sm text-muted-foreground -mt-4">
        These preferences help us personalize your trip plans. They are saved locally on this
        device.
      </p>

      <div className="space-y-6">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="travel-style">Travel Style</Label>
            <Select
              value={prefs.travel_style}
              onValueChange={v => setPrefs(p => ({ ...p, travel_style: v }))}
            >
              <SelectTrigger
                id="travel-style"
                className="h-9 w-full rounded-xl border border-input bg-background px-3 text-sm"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TRAVEL_STYLES.map(opt => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="dietary">Dietary Restriction</Label>
            <Select
              value={prefs.dietary_restriction}
              onValueChange={v => setPrefs(p => ({ ...p, dietary_restriction: v }))}
            >
              <SelectTrigger
                id="dietary"
                className="h-9 w-full rounded-xl border border-input bg-background px-3 text-sm"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DIETARY_OPTIONS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="hotel-tier">Hotel Tier</Label>
            <Select
              value={prefs.hotel_tier}
              onValueChange={v => setPrefs(p => ({ ...p, hotel_tier: v }))}
            >
              <SelectTrigger
                id="hotel-tier"
                className="h-9 w-full rounded-xl border border-input bg-background px-3 text-sm"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {HOTEL_TIERS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="max-stops">Max Flight Stops</Label>
            <Select
              value={String(prefs.max_flight_stops)}
              onValueChange={v => setPrefs(p => ({ ...p, max_flight_stops: Number(v) }))}
            >
              <SelectTrigger
                id="max-stops"
                className="h-9 w-full rounded-xl border border-input bg-background px-3 text-sm"
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MAX_STOPS_OPTIONS.map(opt => (
                  <SelectItem key={opt.value} value={opt.value}>
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <Separator />

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="budget-min">Min Budget (HKD)</Label>
            <Input
              id="budget-min"
              type="number"
              min={0}
              value={prefs.budget_min_hkd}
              onChange={e => setPrefs(p => ({ ...p, budget_min_hkd: Number(e.target.value) }))}
              className="h-9 rounded-xl border border-input bg-background px-3 text-sm"
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="budget-max">Max Budget (HKD)</Label>
            <Input
              id="budget-max"
              type="number"
              min={0}
              value={prefs.budget_max_hkd}
              onChange={e => setPrefs(p => ({ ...p, budget_max_hkd: Number(e.target.value) }))}
              className="h-9 rounded-xl border border-input bg-background px-3 text-sm"
            />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button onClick={handleSave}>{saved ? 'Saved!' : 'Save Preferences'}</Button>
        <Button variant="outline" onClick={handleReset}>
          Reset
        </Button>
        {saved && (
          <p className="text-sm text-green-600 dark:text-green-400">Preferences saved locally.</p>
        )}
      </div>
    </div>
  );
}
