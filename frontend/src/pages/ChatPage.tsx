// ChatPage — Main chat UI with AI travel agent

import { MessageSquare, Settings, Zap } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useChatStore } from '@/store';
import { InputBar } from '@/components/chat/InputBar';
import { apiClient } from '@/services/api';

export function ChatPage() {
  const navigate = useNavigate();
  const messages = useChatStore(s => s.messages);
  const isLoading = useChatStore(s => s.isLoading);
  const isThinking = useChatStore(s => s.isThinking);
  const isLoggedIn = !!localStorage.getItem('token');

  const testLLM = async () => {
    try {
      const res = await apiClient.get('/chat/test-llm');
      alert(`Model: ${res.data.model}\nResponse: ${res.data.response}\nProxy: ${res.data.proxy_enabled}`);
    } catch (e) {
      alert('LLM test failed: ' + (e instanceof Error ? e.message : String(e)));
    }
  };

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
          <div className="ml-auto">
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

          {messages.map(msg => (
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
                {msg.content}
              </div>
            </div>
          ))}

          {/* Thinking indicator — shown while waiting for response */}
          {isLoading && messages.length > 0 && messages[messages.length - 1].role === 'assistant' && messages[messages.length - 1].content === '' && (
            <div className="flex justify-start">
              <div className="max-w-[72%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm bg-muted text-foreground rounded-bl-md">
                <span className="animate-pulse">Thinking...</span>
              </div>
            </div>
          )}
        </div>

        {/* Input bar */}
        <InputBar />
      </main>
    </div>
  );
}
