// LoginPage — Authentication with login / sign-up tabs

import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '@/services/api';

type AuthMode = 'login' | 'signup';

interface AuthResponse {
  access_token: string;
  token_type: string;
}

export function LoginPage() {
  const [mode, setMode] = useState<AuthMode>('login');
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(() => localStorage.getItem('rememberMe') === 'true');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const navigate = useNavigate();

  // Prefill from localStorage when switching to login tab
  useEffect(() => {
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
    if (localStorage.getItem('token')) {
      navigate('/chat');
    }
  }, [navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      if (mode === 'login') {
        const { data } = await apiClient.post<AuthResponse>('/auth/login', {
          email,
          password,
        });
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('rememberMe', String(rememberMe));
        if (rememberMe) {
          localStorage.setItem('user_email', email);
        } else {
          localStorage.removeItem('user_email');
        }
        localStorage.setItem('user_name', username);
        navigate('/chat');
      } else {
        const { data } = await apiClient.post<AuthResponse>('/auth/register', {
          email,
          username,
          password,
        });
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('rememberMe', String(rememberMe));
        localStorage.setItem('user_email', email);
        localStorage.setItem('user_name', username);
        navigate('/chat');
      }
    } catch (err: unknown) {
      if (err && typeof err === 'object' && 'response' in err) {
        const axiosErr = err as { response?: { data?: { detail?: string } } };
        setError(axiosErr.response?.data?.detail ?? 'Something went wrong');
      } else {
        setError('Something went wrong');
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
                  setError(null);
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
                placeholder="you@example.com"
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
                  placeholder="yourname"
                  className="h-9 w-full rounded-xl border border-input bg-background px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
                />
              </div>
            )}

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-foreground" htmlFor="password">
                Password
              </label>
              <input
                id="password"
                type="password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                required
                value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="••••••••"
                className="h-9 w-full rounded-xl border border-input bg-background px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50"
              />
            </div>

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

            {error && <p className="text-xs text-destructive text-center">{error}</p>}

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
