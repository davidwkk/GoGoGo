import { Button } from "@/components/ui/button";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Navigate to="/chat" replace />} />
        <Route path="/login" element={<div>Login Page (TODO)</div>} />
        <Route
          path="/chat"
          element={
            <div className="flex gap-2 p-4">
              <Button>Default</Button>
              <Button variant="outline">Outline</Button>
              <Button variant="destructive">Destructive</Button>
              <Button variant="ghost">Ghost</Button>
            </div>
          }
        />
        <Route path="/trips" element={<div>Trips Page (TODO)</div>} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
