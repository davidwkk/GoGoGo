// App — Root component with routing

import { useEffect } from 'react';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { Toaster } from 'sonner';

import { AppLayout } from '@/components/layout/AppLayout';
import { ChatPage } from '@/pages/ChatPage';
import { LoginPage } from '@/pages/LoginPage';
import { ProfilePage } from '@/pages/ProfilePage';
import { TripPage } from '@/pages/TripPage';
import { useAuthStore } from '@/store';

function App() {
  // Hydrate auth store from localStorage on app boot
  useEffect(() => {
    useAuthStore.getState().initAuth();
  }, []);
  return (
    <BrowserRouter>
      <Toaster position="top-center" richColors />
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route element={<AppLayout />}>
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/trips" element={<TripPage />} />
          <Route path="/chat" element={<ChatPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/chat" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
