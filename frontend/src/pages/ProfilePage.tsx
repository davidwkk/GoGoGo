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

function getPasswordStrength(password: string): { score: number; label: string; color: string } {
  if (!password) return { score: 0, label: '', color: '' };

  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[a-z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;

  if (score <= 2) return { score: 1, label: 'Weak', color: 'bg-red-500' };
  if (score <= 3) return { score: 2, label: 'Fair', color: 'bg-yellow-500' };
  if (score <= 4) return { score: 3, label: 'Good', color: 'bg-blue-500' };
  return { score: 4, label: 'Strong', color: 'bg-green-500' };
}

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
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [changingPassword, setChangingPassword] = useState(false);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState(false);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    toast.dismiss();
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

  const handleChangePassword = async () => {
    if (!localStorage.getItem('access_token')) return;
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
                <div className="flex gap-1">
                  {[1, 2, 3, 4].map(level => (
                    <div
                      key={level}
                      className={`h-1 flex-1 rounded-full transition-colors ${
                        getPasswordStrength(newPassword).score >= level
                          ? getPasswordStrength(newPassword).color
                          : 'bg-muted'
                      }`}
                    />
                  ))}
                </div>
                <p className="text-xs text-muted-foreground">
                  {getPasswordStrength(newPassword).label}
                </p>
              </div>
            )}
            <p className="text-xs text-muted-foreground">
              At least 8 characters, one uppercase letter, one digit
            </p>
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
