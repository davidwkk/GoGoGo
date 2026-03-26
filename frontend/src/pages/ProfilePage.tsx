// ProfilePage — View and edit user profile and travel preferences

import { useCallback, useEffect, useState } from "react";
import { ArrowLeft, User } from "lucide-react";
import { useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { userService, UserPreferences, UserProfile } from "@/services/api";

const TRAVEL_STYLES = [
  { value: "adventure", label: "Adventure" },
  { value: "relaxing", label: "Relaxing" },
  { value: "cultural", label: "Cultural" },
  { value: "foodie", label: "Foodie" },
  { value: "nature", label: "Nature" },
  { value: "shopping", label: "Shopping" },
];

const DIETARY_OPTIONS = [
  { value: "none", label: "None" },
  { value: "vegetarian", label: "Vegetarian" },
  { value: "vegan", label: "Vegan" },
  { value: "halal", label: "Halal" },
  { value: "kosher", label: "Kosher" },
  { value: "gluten_free", label: "Gluten-Free" },
];

const HOTEL_TIERS = [
  { value: "budget", label: "Budget" },
  { value: "mid_range", label: "Mid-Range" },
  { value: "luxury", label: "Luxury" },
];

const MAX_STOPS_OPTIONS = [
  { value: "0", label: "Direct only" },
  { value: "1", label: "Up to 1 stop" },
  { value: "2", label: "Up to 2 stops" },
];

const DEFAULT_PREFERENCES: UserPreferences = {
  travel_style: "relaxing",
  dietary_restriction: "none",
  hotel_tier: "mid_range",
  budget_min_hkd: 5000,
  budget_max_hkd: 20000,
  max_flight_stops: 1,
};

export function ProfilePage() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Form state
  const [username, setUsername] = useState("");
  const [prefs, setPrefs] = useState<UserPreferences>(DEFAULT_PREFERENCES);

  const loadProfile = useCallback(async () => {
    if (!localStorage.getItem("token")) {
      setLoading(false);
      return;
    }
    try {
      setError(null);
      const data = await userService.getProfile();
      setProfile(data);
      setUsername(data.username);
      if (data.preferences) {
        setPrefs(data.preferences);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load profile");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handleSave = async () => {
    if (!localStorage.getItem("token")) return;
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const updated = await userService.updateProfile({
        username,
        preferences: prefs,
      });
      setProfile(updated);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save profile");
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col min-h-screen">
        <div className="p-4">
          <button
            onClick={() => navigate("/chat")}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="size-3.5" />
            Back to chat
          </button>
        </div>
        <div className="flex flex-1 items-center justify-center">
          <p className="text-muted-foreground">Loading profile...</p>
        </div>
      </div>
    );
  }

  if (error && !profile) {
    return (
      <div className="flex flex-col min-h-screen">
        <div className="p-4">
          <button
            onClick={() => navigate("/chat")}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="size-3.5" />
            Back to chat
          </button>
        </div>
        <div className="flex flex-1 flex-col items-center justify-center gap-4">
          <p className="text-destructive">{error}</p>
          <Button variant="outline" onClick={loadProfile}>
            Try again
          </Button>
        </div>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="flex flex-col min-h-screen">
        <div className="p-4">
          <button
            onClick={() => navigate("/chat")}
            className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
          >
            <ArrowLeft className="size-3.5" />
            Back to chat
          </button>
        </div>
        <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
          <User className="size-8 text-muted-foreground" />
          <div>
            <p className="text-sm font-medium">Sign in to view your profile</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Your profile and preferences will appear here
            </p>
          </div>
          <Button variant="outline" onClick={() => window.location.href = "/login"}>
            Sign in
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen">
      {/* Back to Chat */}
      <div className="p-4">
        <button
          onClick={() => navigate("/chat")}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="size-3.5" />
          Back to chat
        </button>
      </div>

      {/* Page content */}
      <div className="max-w-2xl mx-auto py-8 px-4 space-y-6 w-full">
        {/* Page header */}
        <div className="flex items-center gap-3">
          <User className="size-6 text-muted-foreground" />
          <h1 className="text-2xl font-semibold">My Profile</h1>
        </div>

      {/* User info card */}
      <Card>
        <CardHeader>
          <CardTitle>Account</CardTitle>
          <CardDescription>Your login and account details</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Your username"
              minLength={3}
              maxLength={50}
            />
          </div>
          <div className="space-y-2">
            <Label>Email</Label>
            <Input value={profile?.email ?? ""} disabled readOnly />
            <p className="text-xs text-muted-foreground">
              Email cannot be changed
            </p>
          </div>
          {profile?.created_at && (
            <div className="space-y-2">
              <Label>Member since</Label>
              <Input
                value={new Date(profile.created_at).toLocaleDateString()}
                disabled
                readOnly
              />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Travel preferences card */}
      <Card>
        <CardHeader>
          <CardTitle>Travel Preferences</CardTitle>
          <CardDescription>
            Help us personalize your trip plans. These preferences are used when
            generating itineraries.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Row 1: travel style + dietary */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="travel-style">Travel Style</Label>
              <Select
                value={prefs.travel_style}
                onValueChange={(v) =>
                  setPrefs((p) => ({ ...p, travel_style: v }))
                }
              >
                <SelectTrigger id="travel-style">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TRAVEL_STYLES.map((opt) => (
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
                onValueChange={(v) =>
                  setPrefs((p) => ({ ...p, dietary_restriction: v }))
                }
              >
                <SelectTrigger id="dietary">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DIETARY_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Row 2: hotel tier + max stops */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="hotel-tier">Hotel Tier</Label>
              <Select
                value={prefs.hotel_tier}
                onValueChange={(v) =>
                  setPrefs((p) => ({ ...p, hotel_tier: v }))
                }
              >
                <SelectTrigger id="hotel-tier">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {HOTEL_TIERS.map((opt) => (
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
                onValueChange={(v) =>
                  setPrefs((p) => ({ ...p, max_flight_stops: Number(v) }))
                }
              >
                <SelectTrigger id="max-stops">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MAX_STOPS_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <Separator />

          {/* Row 3: budget range */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label htmlFor="budget-min">Min Budget (HKD)</Label>
              <Input
                id="budget-min"
                type="number"
                min={0}
                value={prefs.budget_min_hkd}
                onChange={(e) =>
                  setPrefs((p) => ({
                    ...p,
                    budget_min_hkd: Number(e.target.value),
                  }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="budget-max">Max Budget (HKD)</Label>
              <Input
                id="budget-max"
                type="number"
                min={0}
                value={prefs.budget_max_hkd}
                onChange={(e) =>
                  setPrefs((p) => ({
                    ...p,
                    budget_max_hkd: Number(e.target.value),
                  }))
                }
              />
            </div>
          </div>
        </CardContent>
      </Card>
      </div>

      {/* Save row */}
      <div className="flex items-center gap-4">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save Changes"}
        </Button>
        {success && (
          <p className="text-sm text-green-600 dark:text-green-400">
            Profile saved successfully!
          </p>
        )}
        {error && profile && (
          <p className="text-sm text-destructive">{error}</p>
        )}
      </div>
    </div>
  );
}
