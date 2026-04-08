// ProfilePage — View and edit user account details

import { Eye, EyeOff, LogOut, User } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { UserProfile, userService } from '@/services/api';
import { useAuthStore } from '@/store';

interface AuthError {
  userMessage?: string;
  message?: string;
}

export function ProfilePage() {
  const navigate = useNavigate();
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  // Set error need to be prettier, use custom error component
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Form state
  const [username, setUsername] = useState('');

  // Password change state
  const [currentPassword, setCurrentPassword] = useState('');
  const [tripCommands, setTripCommands] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState(false);

  const handleLogout = () => {
    useAuthStore.getState().clearAuth();
    toast.dismiss();
    navigate('/login');
  };

  const loadProfile = useCallback(async () => {
    if (!useAuthStore.getState().token) {
      setLoading(false);
      return;
    }
    try {
      setError(null);
      const data = await userService.getProfile();
      setProfile(data);
      setUsername(data.username);
      setTripCommands(data.preferences?.trip_planning_commands ?? '');
    } catch (err) {
      const authErr = err as AuthError;
      if (authErr.userMessage) {
        setError(authErr.userMessage);
        // Redirect to login after showing the message
        setTimeout(() => {
          useAuthStore.getState().clearAuth();
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
    if (!useAuthStore.getState().token) return;
    setSaving(true);
    setError(null);
    setSuccess(false);
    try {
      const updated = await userService.updateProfile({
        username,
        preferences: { ...profile?.preferences, trip_planning_commands: tripCommands },
      });
      setProfile(updated);
      const { token } = useAuthStore.getState();
      if (token) {
        useAuthStore
          .getState()
          .setAuth({ email: profile!.email, username: updated.username }, token);
      }
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save profile');
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async () => {
    if (!useAuthStore.getState().token) return;
    setPasswordError(null);

    if (newPassword.length < 8) {
      setPasswordError('New password must be at least 8 characters');
      return;
    }
    if (!/[A-Z]/.test(newPassword)) {
      setPasswordError('New password must contain at least one uppercase letter');
      return;
    }
    if (!/[0-9]/.test(newPassword)) {
      setPasswordError('New password must contain at least one digit');
      return;
    }
    if (newPassword !== confirmPassword) {
      setPasswordError('Passwords do not match');
      return;
    }

    setChangingPassword(true);
    try {
      await userService.changePassword(currentPassword, newPassword);
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      setPasswordSuccess(true);
      setTimeout(() => setPasswordSuccess(false), 3000);
    } catch (err) {
      const apiErr = err as { detail?: string };
      setPasswordError(apiErr.detail || 'Failed to change password');
    } finally {
      setChangingPassword(false);
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

      {/* Password change card */}
      <Card>
        <CardHeader>
          <CardTitle>Change Password</CardTitle>
          <CardDescription>Update your account password</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="current-password">Current Password</Label>
            <div className="relative">
              <Input
                id="current-password"
                type={showCurrentPassword ? 'text' : 'password'}
                value={currentPassword}
                onChange={e => setCurrentPassword(e.target.value)}
                placeholder="Enter current password"
                className="pr-10"
              />
              <button
                type="button"
                onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showCurrentPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="new-password">New Password</Label>
            <div className="relative">
              <Input
                id="new-password"
                type={showNewPassword ? 'text' : 'password'}
                value={newPassword}
                onChange={e => setNewPassword(e.target.value)}
                placeholder="Enter new password"
                className="pr-10"
                minLength={8}
              />
              <button
                type="button"
                onClick={() => setShowNewPassword(!showNewPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              >
                {showNewPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
            {newPassword && (
              <div className="space-y-1">
                <p className="text-xs text-muted-foreground">Password must have:</p>
                <div className="flex flex-col gap-0.5">
                  <div className="flex items-center gap-2">
                    <div
                      className={`size-1.5 rounded-full ${newPassword.length >= 8 ? 'bg-green-500' : 'bg-muted'}`}
                    />
                    <span
                      className={`text-xs ${newPassword.length >= 8 ? 'text-green-600' : 'text-muted-foreground'}`}
                    >
                      At least 8 characters
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div
                      className={`size-1.5 rounded-full ${/[A-Z]/.test(newPassword) ? 'bg-green-500' : 'bg-muted'}`}
                    />
                    <span
                      className={`text-xs ${/[A-Z]/.test(newPassword) ? 'text-green-600' : 'text-muted-foreground'}`}
                    >
                      One uppercase letter
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div
                      className={`size-1.5 rounded-full ${/[a-z]/.test(newPassword) ? 'bg-green-500' : 'bg-muted'}`}
                    />
                    <span
                      className={`text-xs ${/[a-z]/.test(newPassword) ? 'text-green-600' : 'text-muted-foreground'}`}
                    >
                      One lowercase letter
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div
                      className={`size-1.5 rounded-full ${/[0-9]/.test(newPassword) ? 'bg-green-500' : 'bg-muted'}`}
                    />
                    <span
                      className={`text-xs ${/[0-9]/.test(newPassword) ? 'text-green-600' : 'text-muted-foreground'}`}
                    >
                      One number
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm-password">Confirm New Password</Label>
            <Input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              placeholder="Confirm new password"
            />
          </div>
          {passwordError && <p className="text-sm text-destructive">{passwordError}</p>}
          {passwordSuccess && (
            <p className="text-sm text-green-600 dark:text-green-400">
              Password changed successfully!
            </p>
          )}
          <Button onClick={handleChangePassword} disabled={changingPassword}>
            {changingPassword ? 'Changing...' : 'Change Password'}
          </Button>
        </CardContent>
      </Card>

      {/* Trip Planning Commands card */}
      <Card>
        <CardHeader>
          <CardTitle>Trip Planning Preferences</CardTitle>
          <CardDescription>Custom rules and instructions for trip planning</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="trip-commands">Custom Commands / Rules</Label>
            <textarea
              id="trip-commands"
              value={tripCommands}
              onChange={e => setTripCommands(e.target.value)}
              placeholder="E.g., Prioritize commercial activities, Always suggest budget options..."
              rows={4}
              className="w-full rounded-xl border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 resize-none"
            />
            <p className="text-xs text-muted-foreground">
              These instructions will be sent to the AI when planning trips. E.g., &quot;Prioritize
              shopping areas&quot;, &quot;Suggest halal food options&quot;.
            </p>
          </div>
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
