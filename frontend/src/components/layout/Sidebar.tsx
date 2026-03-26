// Sidebar — Left navigation bar with icon links

import { useLocation, useNavigate } from 'react-router-dom';
import { LogOut, MessageSquare, Map, User } from 'lucide-react';

const navItems = [
  { icon: MessageSquare, label: 'Chat', path: '/chat' },
  { icon: Map, label: 'Trips', path: '/trips' },
  { icon: User, label: 'Profile', path: '/profile' },
];

export function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/login');
  };

  return (
    <aside className="flex flex-col items-center gap-6 py-6 w-14 bg-background border-r">
      {/* Logo */}
      <button
        onClick={() => navigate('/chat')}
        className="mb-2 flex items-center justify-center rounded-xl bg-black text-white size-10 font-semibold text-sm hover:opacity-80 transition-opacity"
      >
        GG
      </button>

      {/* Nav icons */}
      <nav className="flex flex-col items-center gap-2 flex-1">
        {navItems.map(({ icon: Icon, label, path }) => {
          const active = location.pathname === path;
          return (
            <button
              key={path}
              onClick={() => navigate(path)}
              title={label}
              className={`flex items-center justify-center rounded-xl size-10 transition-all ${
                active
                  ? 'bg-black text-white'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground'
              }`}
            >
              <Icon className="size-5" />
            </button>
          );
        })}
      </nav>

      {/* Logout */}
      <button
        onClick={handleLogout}
        title="Logout"
        className="flex items-center justify-center rounded-xl size-10 text-muted-foreground hover:bg-muted hover:text-foreground transition-all"
      >
        <LogOut className="size-5" />
      </button>
    </aside>
  );
}
