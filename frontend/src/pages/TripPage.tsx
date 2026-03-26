// TripPage — View/edit trip itineraries

import { ArrowLeft, Map } from "lucide-react";
import { useNavigate } from "react-router-dom";

export function TripPage() {
  const navigate = useNavigate();
  const isLoggedIn = !!localStorage.getItem("token");

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

      <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center">
        <div className="flex items-center justify-center rounded-full bg-muted size-12">
          <Map className="size-5 text-muted-foreground" />
        </div>
        {isLoggedIn ? (
          <>
            <h1 className="text-xl font-semibold">My Trips</h1>
            <p className="text-xs text-muted-foreground">Your saved trips will appear here...</p>
          </>
        ) : (
          <>
            <div>
              <p className="text-sm font-medium">Sign in to view your trips</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                Your saved itineraries will appear here
              </p>
            </div>
            <button
              onClick={() => navigate("/login")}
              className="h-8 rounded-xl bg-black text-white px-4 text-sm font-medium hover:opacity-80 transition-opacity"
            >
              Sign in
            </button>
          </>
        )}
      </div>
    </div>
  );
}
