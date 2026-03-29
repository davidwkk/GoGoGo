// ChatPage — Main chat UI with AI travel agent

import { useState, useEffect, useRef } from 'react';
import { MessageSquare, Settings, Zap, PlusCircle, Sparkles, Calendar, MapPin } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useChatStore } from '@/store';
import { InputBar } from '@/components/chat/InputBar';
import { apiClient } from '@/services/api';
import { tripService } from '@/services/tripService';
import type { TripItinerary, Flight, DayPlan } from '@/types/trip';
import { FlightCard } from '@/components/trip/FlightCard';
import { ActivityCard } from '@/components/trip/ActivityCard';

function StreamingMessage({ content }: { content: string }) {
  const [displayedWords, setDisplayedWords] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // Reset when content changes
    setDisplayedWords(0);

    // Clear any existing interval
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
    }

    const words = content.split(/\s+/);
    if (words.length === 0) return;

    // Reveal 1 word every 50ms for natural "talking" feel
    intervalRef.current = setInterval(() => {
      setDisplayedWords(prev => {
        if (prev >= words.length) {
          if (intervalRef.current) clearInterval(intervalRef.current);
          return prev;
        }
        return prev + 1;
      });
    }, 50);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [content]);

  const words = content.split(/\s+/);
  const displayed = words.slice(0, displayedWords).join(' ');
  const remaining = words.slice(displayedWords).join(' ');

  return (
    <>
      {displayed}
      {remaining && <span className="animate-pulse">{remaining[0]}</span>}
      {remaining.slice(1)}
    </>
  );
}

// Inline Itinerary Display — shown after demo trip generation
function ItineraryDisplay({ itinerary }: { itinerary: TripItinerary }) {
  const hotel = itinerary.hotels?.[0];
  const nights = hotel
    ? Math.max(
        1,
        Math.ceil(
          (new Date(hotel.check_out_date).getTime() - new Date(hotel.check_in_date).getTime()) /
            (1000 * 60 * 60 * 24)
        )
      )
    : 1;
  const minTotal = (hotel?.price_per_night_min_hkd || 0) * nights;
  const maxTotal = (hotel?.price_per_night_max_hkd || 0) * nights;

  return (
    <div className="w-full max-w-3xl mx-auto bg-white rounded-3xl border border-slate-100 shadow-xl overflow-hidden">
      {/* Header */}
      <div className="bg-linear-to-r from-slate-900 to-slate-800 p-8 text-white">
        <div className="flex items-center gap-2 text-blue-400 mb-4 font-black text-[10px] uppercase tracking-[0.3em]">
          <Sparkles className="size-4" /> Demo Trip Generated
        </div>
        <h2 className="text-4xl font-black tracking-tight mb-4">{itinerary.destination}</h2>
        <div className="flex items-center gap-4 text-sm text-slate-400">
          <span className="flex items-center gap-1">
            <Calendar className="size-3.5" />
            {itinerary.duration_days} days
          </span>
          <span className="flex items-center gap-1">
            <MapPin className="size-3.5" />
            {itinerary.flights?.length || 0} flights
          </span>
        </div>
      </div>

      <div className="p-8 space-y-8">
        {/* Summary */}
        {itinerary.summary && (
          <div className="bg-slate-50 rounded-2xl p-6 border border-slate-100 italic text-slate-600">
            "{itinerary.summary}"
          </div>
        )}

        {/* Weather Tip */}
        {itinerary.weather_summary && (
          <div className="bg-blue-50 rounded-2xl p-5 border border-blue-100 flex gap-4 items-start">
            <div className="bg-blue-600 text-white px-3 py-1 rounded-full text-[10px] font-black uppercase tracking-widest whitespace-nowrap h-fit">
              Travel Tip
            </div>
            <p className="text-xs text-blue-800 leading-relaxed">{itinerary.weather_summary}</p>
          </div>
        )}

        {/* Flights */}
        {itinerary.flights && itinerary.flights.length > 0 && (
          <div>
            <div className="flex items-center gap-3 mb-5">
              <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">
                Flights
              </span>
              <div className="h-px flex-1 bg-slate-100" />
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {itinerary.flights.map((f: Flight, i: number) => (
                <FlightCard key={i} flight={f} />
              ))}
            </div>
          </div>
        )}

        {/* Days */}
        <div>
          <div className="flex items-center gap-3 mb-6">
            <span className="text-[10px] font-black uppercase tracking-widest text-slate-400">
              Itinerary
            </span>
            <div className="h-px flex-1 bg-slate-100" />
          </div>
          <div className="space-y-10">
            {itinerary.days?.map((day: DayPlan) => (
              <div key={day.day_number}>
                <div className="flex items-center gap-3 mb-5">
                  <div className="size-9 rounded-xl bg-slate-900 text-white flex items-center justify-center font-black text-sm">
                    {day.day_number}
                  </div>
                  <div>
                    <p className="font-black text-base text-slate-900">Day {day.day_number}</p>
                    <p className="text-[10px] text-slate-400 font-bold uppercase tracking-widest">
                      {day.date}
                    </p>
                  </div>
                </div>
                <div className="ml-2 border-l-2 border-slate-100 pl-4 space-y-3">
                  <ActivityCard activity={day.morning?.[0]} label="Morning" />
                  <ActivityCard activity={day.afternoon?.[0]} label="Afternoon" />
                  <ActivityCard activity={day.evening?.[0]} label="Evening" />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Hotel */}
        {hotel && (
          <div className="bg-slate-900 rounded-3xl p-8 text-white relative overflow-hidden">
            <div className="absolute -right-8 -top-8 size-32 bg-blue-600/10 rounded-full blur-2xl" />
            <div className="relative">
              <div className="flex justify-between items-start mb-4">
                <span className="px-3 py-1 bg-blue-600 rounded-full text-[10px] font-black uppercase tracking-[0.2em]">
                  Stay
                </span>
                <div className="text-right">
                  <p className="text-[10px] text-slate-500 uppercase tracking-widest">Nightly</p>
                  <p className="text-sm font-bold text-blue-400">
                    HKD {hotel.price_per_night_min_hkd?.toLocaleString()} –{' '}
                    {hotel.price_per_night_max_hkd?.toLocaleString()}
                  </p>
                </div>
              </div>
              <h4 className="text-3xl font-black tracking-tight mb-3">{hotel.name}</h4>
              <div className="flex flex-wrap gap-6 text-sm text-slate-300">
                <span>Check-in: {hotel.check_in_date}</span>
                <span>Check-out: {hotel.check_out_date}</span>
                <span>{nights} nights</span>
              </div>
              <div className="mt-6 pt-5 border-t border-white/10 flex justify-between items-end">
                <div>
                  <p className="text-[10px] text-blue-300 uppercase tracking-widest mb-1">
                    Total Estimate
                  </p>
                  <p className="text-2xl font-black">
                    HKD {minTotal.toLocaleString()} – {maxTotal.toLocaleString()}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Loading skeleton while demo generates
function DemoLoadingSkeleton() {
  return (
    <div className="w-full max-w-3xl mx-auto bg-white rounded-3xl border border-slate-100 shadow-xl overflow-hidden">
      <div className="bg-linear-to-r from-slate-900 to-slate-800 p-8">
        <div className="h-4 w-32 bg-white/10 rounded mb-4 animate-pulse" />
        <div className="h-10 w-64 bg-white/10 rounded animate-pulse" />
      </div>
      <div className="p-8 space-y-6">
        <div className="h-20 bg-slate-50 rounded-2xl animate-pulse" />
        <div className="h-32 bg-slate-50 rounded-2xl animate-pulse" />
        <div className="h-48 bg-slate-50 rounded-2xl animate-pulse" />
      </div>
    </div>
  );
}

export function ChatPage() {
  const navigate = useNavigate();
  const messages = useChatStore(s => s.messages);
  const isLoading = useChatStore(s => s.isLoading);
  const isThinking = useChatStore(s => s.isThinking);
  const thinkingSteps = useChatStore(s => s.thinkingSteps);
  const isLoggedIn = !!localStorage.getItem('access_token');
  const clearMessages = useChatStore(s => s.clearMessages);
  const setSessionId = useChatStore(s => s.setSessionId);
  const abortController = useChatStore(s => s.abortController);

  const [demoItinerary, setDemoItinerary] = useState<TripItinerary | null>(null);
  const [showDemoLoading, setShowDemoLoading] = useState(false);

  const startNewChat = () => {
    // Cancel any in-progress stream first
    if (abortController) {
      abortController.abort();
    }
    clearMessages();
    setSessionId(null);
    setDemoItinerary(null);
    localStorage.removeItem('guest_uid');
  };

  const testLLM = async () => {
    try {
      const res = await apiClient.get('/chat/test-llm');
      alert(
        `Model: ${res.data.model}\nResponse: ${res.data.response}\nProxy: ${res.data.proxy_enabled}`
      );
    } catch (e) {
      alert('LLM test failed: ' + (e instanceof Error ? e.message : String(e)));
    }
  };

  const generateDemoTrip = async () => {
    if (showDemoLoading || isLoading) return;
    setShowDemoLoading(true);
    setDemoItinerary(null);
    try {
      const demo = await tripService.getDemoTrip();
      setDemoItinerary(demo.itinerary);
    } catch (err) {
      console.error('Failed to load demo trip:', err);
      alert('Demo trip not available. Please ensure the database is seeded.');
    } finally {
      setShowDemoLoading(false);
    }
  };

  // Determine if the last message is still streaming
  const lastMsg = messages[messages.length - 1];
  const isStreaming = isLoading && lastMsg?.role === 'assistant';

  return (
    <div className="flex h-screen bg-background">
      {/* Main chat area */}
      <main className="flex flex-col flex-1">
        {/* Header */}
        <header className="flex items-center gap-3 px-6 py-4 border-b">
          <div className="flex items-center justify-center rounded-xl bg-black text-white size-8">
            <MessageSquare className="size-4" />
          </div>
          <div>
            <h1 className="text-sm font-semibold">GoGoGo</h1>
            <p className="text-xs text-muted-foreground">AI Travel Agent</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            {messages.length > 0 && (
              <button
                onClick={startNewChat}
                className="flex items-center gap-1.5 h-8 rounded-xl border border-border bg-background px-3 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
              >
                <PlusCircle className="size-3" />
                New Chat
              </button>
            )}
            <button
              onClick={generateDemoTrip}
              disabled={isLoading || showDemoLoading}
              className="flex items-center gap-1.5 h-8 rounded-xl bg-linear-to-r from-blue-600 to-blue-500 text-white px-3 text-xs font-medium hover:from-blue-500 hover:to-blue-400 transition-colors disabled:opacity-50"
            >
              <Sparkles className="size-3" />
              {showDemoLoading ? 'Generating...' : 'Demo Trip'}
            </button>
            <button
              onClick={testLLM}
              className="flex items-center gap-1.5 h-8 rounded-xl bg-yellow-500 text-black px-3 text-xs font-medium hover:bg-yellow-400 transition-colors"
            >
              <Zap className="size-3" />
              Test LLM
            </button>
          </div>
        </header>

        {/* Message list */}
        <div className="flex-1 overflow-y-auto px-6 py-6 space-y-4">
          {messages.length === 0 && !isLoading && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
              <div className="flex items-center justify-center rounded-full bg-muted size-12">
                <MessageSquare className="size-5 text-muted-foreground" />
              </div>
              <div>
                <p className="text-sm font-medium">Start your trip planning</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  Ask me anything about destinations, flights, hotels, or attractions
                </p>
              </div>
              {!isLoggedIn && (
                <div className="flex items-center gap-2 mt-1">
                  <button
                    onClick={() => navigate('/login')}
                    className="h-8 rounded-xl bg-black text-white px-4 text-sm font-medium hover:opacity-80 transition-opacity"
                  >
                    Sign in
                  </button>
                  <button
                    onClick={() => navigate('/preferences')}
                    className="flex items-center gap-1.5 h-8 rounded-xl border border-border bg-background px-4 text-sm font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
                  >
                    <Settings className="size-3.5" />
                    Set preferences
                  </button>
                </div>
              )}
            </div>
          )}

          {isLoading && messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-3 text-center">
              <div className="flex items-center justify-center rounded-full bg-muted size-12 animate-pulse">
                <MessageSquare className="size-5 text-muted-foreground" />
              </div>
              <p className="text-sm text-muted-foreground">Thinking...</p>
            </div>
          )}

          {messages.map((msg, idx) => {
            const isLastAssistant = idx === messages.length - 1 && msg.role === 'assistant';
            return (
              <div
                key={msg.id}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-[72%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
                    msg.role === 'user'
                      ? 'bg-black text-white rounded-br-md'
                      : 'bg-muted text-foreground rounded-bl-md'
                  }`}
                >
                  {isLastAssistant && isStreaming ? (
                    <StreamingMessage content={msg.content} />
                  ) : (
                    msg.content
                  )}
                </div>
              </div>
            );
          })}

          {/* Thinking indicator — shown while waiting for first content */}
          {(isThinking || thinkingSteps.length > 0) && (
            <div className="flex justify-start">
              <div className="max-w-[72%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm bg-muted text-foreground rounded-bl-md space-y-1">
                {thinkingSteps.length > 0 ? (
                  <div className="space-y-1">
                    {thinkingSteps.map((step, i) => (
                      <div
                        key={i}
                        className="flex items-center gap-1.5 text-xs text-muted-foreground"
                      >
                        {i === thinkingSteps.length - 1 && (
                          <span className="animate-pulse h-1.5 w-1.5 rounded-full bg-yellow-500 inline-block" />
                        )}
                        {step}
                      </div>
                    ))}
                  </div>
                ) : (
                  <span className="animate-pulse">Thinking...</span>
                )}
              </div>
            </div>
          )}

          {/* Demo trip result — shown inline after generation */}
          {showDemoLoading && <DemoLoadingSkeleton />}

          {demoItinerary && !showDemoLoading && (
            <div className="flex justify-start">
              <ItineraryDisplay itinerary={demoItinerary} />
            </div>
          )}
        </div>

        {/* Input bar */}
        <InputBar onItinerary={setDemoItinerary} />
      </main>
    </div>
  );
}
