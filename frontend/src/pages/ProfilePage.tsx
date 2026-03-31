// ProfilePage — View and edit user account details

import { useCallback, useEffect, useState } from 'react';
import { LogOut, User } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { userService, UserProfile } from '@/services/api';

interface AuthError {
  userMessage?: string;
  message?: string;
}

export function ProfilePage() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Form state
  const [username, setUsername] = useState('');

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    navigate('/login');
  };

  const loadProfile = useCallback(async () => {
    if (!localStorage.getItem('access_token')) {
      setLoading(false);
      return;
    }
    try {
      setError(null);
      const data = await userService.getProfile();
      setProfile(data);
      setUsername(data.username);
    } catch (err) {
      const authErr = err as AuthError;
      if (authErr.userMessage) {
        setError(authErr.userMessage);
        // Redirect to login after showing the message
        setTimeout(() => {
          localStorage.removeItem('access_token');
          navigate('/login');
        }, 3000);
      } else {
        setError(err instanceof Error ? err.message : 'Failed to load profile');
      }
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  const handleSave = async () => {
    if (!localStorage.getItem('access_token')) return;
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const updated = await userService.updateProfile({ username });
      setProfile(updated);
      localStorage.setItem('user_name', updated.username);
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save profile');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <p className="text-muted-foreground">Loading profile...</p>
      </div>
    );
  }

  if (error && !profile) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <p className="text-destructive">{error}</p>
        <Button variant="outline" onClick={loadProfile}>
          Try again
        </Button>
      </div>
    );
  }

  if (!profile) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-3 text-center">
        <User className="size-8 text-muted-foreground" />
        <div>
          <p className="text-sm font-medium">Sign in to view your profile</p>
          <p className="text-xs text-muted-foreground mt-0.5">
            Your profile and preferences will appear here
          </p>
        </div>
        <Button
          onClick={() => (window.location.href = '/login')}
          className="h-8 rounded-xl bg-black text-white px-4 text-sm font-medium hover:opacity-80 transition-opacity"
        >
          Sign in
        </Button>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto py-8 px-4 space-y-6">
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
              onChange={e => setUsername(e.target.value)}
              placeholder="Your username"
              minLength={3}
              maxLength={50}
            />
          </div>
          <div className="space-y-2">
            <Label>Email</Label>
            <Input value={profile?.email ?? ''} disabled readOnly />
            <p className="text-xs text-muted-foreground">Email cannot be changed</p>
          </div>
          {profile?.created_at && (
            <div className="space-y-2">
              <Label>Member since</Label>
              <Input value={new Date(profile.created_at).toLocaleDateString()} disabled readOnly />
            </div>
          )}
        </CardContent>
      </Card>

      {/* Save row */}
      <div className="flex items-center gap-4">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Changes'}
        </Button>
        {success && (
          <p className="text-sm text-green-600 dark:text-green-400">Profile saved successfully!</p>
        )}
        {error && profile && <p className="text-sm text-destructive">{error}</p>}
        <div className="ml-auto">
          <Button variant="outline" onClick={handleLogout}>
            <LogOut className="size-4 mr-1.5" />
            Logout
          </Button>
        </div>
      </div>
    </div>
  );
}
