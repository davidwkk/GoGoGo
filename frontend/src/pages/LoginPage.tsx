// LoginPage — Authentication with login / sign-up tabs

import { authService } from '@/services/authService';
import { Eye, EyeOff } from 'lucide-react';
import { useChatStore, useAuthStore } from '@/store';
import { AuthResponse } from '@/types/auth';

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from 'sonner';

type AuthMode = 'login' | 'signup';

export function LoginPage() {
  const [mode, setMode] = useState<AuthMode>('login');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(() => localStorage.getItem('rememberMe') === 'true');
  const [loading, setLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const navigate = useNavigate();

  // Clear password when switching between login/signup modes
  useEffect(() => {
    setPassword('');
    setConfirmPassword('');
    if (mode === 'login') {
      setEmail(localStorage.getItem('user_email') ?? '');
      setUsername(localStorage.getItem('user_name') ?? '');
    } else {
      setEmail('');
      setUsername('');
    }
  }, [mode]);

  // Auto-redirect to chat if already logged in
  useEffect(() => {
    if (useAuthStore.getState().token) {
      navigate('/chat');
    }
  }, [navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      if (mode === 'login') {
        const response: AuthResponse = await authService.login(email, password);
        const { setAuth } = useAuthStore.getState();
        setAuth({ email, username }, response.access_token);
        localStorage.setItem('rememberMe', String(rememberMe));
        if (!rememberMe) {
          localStorage.removeItem('user_email');
        }
        // Clear messages and create new session for fresh start
        useChatStore.getState().clearMessages();
        useChatStore.getState().setSessionId(null);
        navigate('/chat');
      } else {
        // Client-side password validation
        if (password.length < 8) {
          toast.error('Password must be at least 8 characters');
          setLoading(false);
          return;
        }
        if (!/[A-Z]/.test(password)) {
          toast.error('Password must contain at least one uppercase letter');
          setLoading(false);
          return;
        }
        if (!/[a-z]/.test(password)) {
          toast.error('Password must contain at least one lowercase letter');
          setLoading(false);
          return;
        }
        if (!/[0-9]/.test(password)) {
          toast.error('Password must contain at least one number');
          setLoading(false);
          return;
        }
        if (password !== confirmPassword) {
          toast.error('Passwords do not match');
          setLoading(false);
          return;
        }

        const response: AuthResponse = await authService.register(email, username, password);
        const { setAuth } = useAuthStore.getState();
        setAuth({ email, username }, response.access_token);
        localStorage.setItem('rememberMe', String(rememberMe));
        // Clear messages and create new session for fresh start
        useChatStore.getState().clearMessages();
        useChatStore.getState().setSessionId(null);
        navigate('/chat');
      }
    } catch (err: unknown) {
      // Because of our interceptor, we know `err` is our APIError envelope
      const apiErr = err as import('@/services/api').APIError;
      if (apiErr.statusCode === 409) {
        toast.error('An account with this email already exists');
      } else if (apiErr.statusCode === 401) {
        toast.error('Invalid email or password');
      } else {
        toast.error(apiErr.detail || 'Something went wrong. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted/30 px-4">
      <div className="w-full max-w-sm space-y-6">
        {/* Logo */}
        <div className="flex flex-col items-center gap-2">
          <div className="flex items-center justify-center rounded-2xl bg-black text-white size-12 font-semibold text-sm">
            GG
          </div>
          <h1 className="text-xl font-semibold tracking-tight">GoGoGo</h1>
          <p className="text-xs text-muted-foreground text-center">Your AI-powered travel agent</p>
        </div>

        {/* Card */}
        <div className="rounded-2xl border bg-card p-6 shadow-sm space-y-5">
          {/* Tab switcher */}
          <div className="flex rounded-xl bg-muted p-0.5">
            {(['login', 'signup'] as AuthMode[]).map(m => (
              <button
                key={m}
                type="button"
                onClick={() => {
                  setMode(m);
                }}
                className={`flex-1 rounded-lg py-1.5 text-sm font-medium transition-all ${
                  mode === m
                    ? 'bg-background text-foreground shadow-sm'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {m === 'login' ? 'Sign in' : 'Sign up'}
              </button>
            ))}
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-foreground" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="your-email@example.com"
                className="h-9 w-full rounded-xl border border-input bg-background px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
              />
            </div>

            {mode === 'signup' && (
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-foreground" htmlFor="username">
                  Username
                </label>
                <input
                  id="username"
                  type="text"
                  autoComplete="username"
                  required
                  minLength={3}
                  maxLength={50}
                  value={username}
                  onChange={e => setUsername(e.target.value)}
                  placeholder="your-username"
                  className="h-9 w-full rounded-xl border border-input bg-background px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
                />
              </div>
            )}

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-foreground" htmlFor="password">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                  required
                  value={password}
                  onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="h-9 w-full rounded-xl border border-input bg-background px-3 pr-10 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {mode === 'signup' && (
                <div className="space-y-1">
                  <p className="text-xs text-muted-foreground">Password must have:</p>
                  <div className="flex flex-col gap-0.5">
                    <div className="flex items-center gap-2">
                      <div
                        className={`size-1.5 rounded-full ${password.length >= 8 ? 'bg-green-500' : 'bg-muted'}`}
                      />
                      <span
                        className={`text-xs ${password.length >= 8 ? 'text-green-600' : 'text-muted-foreground'}`}
                      >
                        At least 8 characters
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div
                        className={`size-1.5 rounded-full ${/[A-Z]/.test(password) ? 'bg-green-500' : 'bg-muted'}`}
                      />
                      <span
                        className={`text-xs ${/[A-Z]/.test(password) ? 'text-green-600' : 'text-muted-foreground'}`}
                      >
                        One uppercase letter
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div
                        className={`size-1.5 rounded-full ${/[a-z]/.test(password) ? 'bg-green-500' : 'bg-muted'}`}
                      />
                      <span
                        className={`text-xs ${/[a-z]/.test(password) ? 'text-green-600' : 'text-muted-foreground'}`}
                      >
                        One lowercase letter
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <div
                        className={`size-1.5 rounded-full ${/[0-9]/.test(password) ? 'bg-green-500' : 'bg-muted'}`}
                      />
                      <span
                        className={`text-xs ${/[0-9]/.test(password) ? 'text-green-600' : 'text-muted-foreground'}`}
                      >
                        One number
                      </span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {mode === 'signup' && (
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-foreground" htmlFor="confirm-password">
                  Confirm Password
                </label>
                <div className="relative">
                  <input
                    id="confirm-password"
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="new-password"
                    required
                    value={confirmPassword}
                    onChange={e => setConfirmPassword(e.target.value)}
                    placeholder="••••••••"
                    className="h-9 w-full rounded-xl border border-input bg-background px-3 pr-10 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
                {confirmPassword && password !== confirmPassword && (
                  <p className="text-xs text-red-500">Passwords do not match</p>
                )}
              </div>
            )}

            {mode === 'login' && (
              <div className="flex items-center gap-2">
                <input
                  id="rememberMe"
                  type="checkbox"
                  checked={rememberMe}
                  onChange={e => setRememberMe(e.target.checked)}
                  className="h-4 w-4 rounded border-input accent-black"
                />
                <label
                  htmlFor="rememberMe"
                  className="text-xs text-muted-foreground cursor-pointer"
                >
                  Remember me
                </label>
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="h-9 w-full rounded-xl bg-black text-white text-sm font-medium hover:opacity-80 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Please wait...' : mode === 'login' ? 'Sign in' : 'Create account'}
            </button>
          </form>
        </div>

        <button
          type="button"
          onClick={() => {
            // Clear existing messages and session for fresh guest experience
            useChatStore.getState().clearMessages();
            useChatStore.getState().setSessionId(null);
            if (!localStorage.getItem('guest_uid')) {
              localStorage.setItem('guest_uid', crypto.randomUUID());
            }
            navigate('/chat');
          }}
          className="h-9 w-full rounded-xl border border-border bg-background text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
        >
          Continue as Guest
        </button>

        <p className="text-center text-xs text-muted-foreground">
          By continuing, you agree to our Terms of Service
        </p>
      </div>
    </div>
  );
}
