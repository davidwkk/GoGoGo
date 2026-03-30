// InputBar — Text input + Send + Generate Trip Plan + Voice input
// Wired to useChat hook; voice button uses ASR to populate input field.

import { Map, Send } from 'lucide-react';
import { useRef, useState } from 'react';

import { Button } from '@/components/ui/button';
import { VoiceButton } from '@/components/voice/VoiceButton';
import { useASR } from '@/hooks/useASR';
import { useChat } from '@/hooks/useChat';
import { useChatStore } from '@/store';
import type { TripItinerary } from '@/types/trip';

interface InputBarProps {
  disabled?: boolean;
  onItinerary?: (itinerary: TripItinerary) => void;
}

export function InputBar({ disabled, onItinerary }: InputBarProps) {
  const [text, setText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const voiceAvailable = useChatStore(s => s.voiceAvailable);
  const isLoading = useChatStore(s => s.isLoading);
  const addMessage = useChatStore(s => s.addMessage);
  const setThinking = useChatStore(s => s.setThinking);
  const { sendMessage } = useChat({ onItinerary });
  const { isListening, startListening, stopListening } = useASR({
    onTranscript: result => {
      // Append transcript to existing text (allows multiple utterances)
      setText(prev => {
        const next = prev ? `${prev} ${result.transcript}` : result.transcript;
        return next;
      });
    },
    onError: error => {
      console.warn('ASR error:', error);
    },
  });

  const adjustTextareaHeight = () => {
    const textarea = textareaRef.current;
    if (textarea) {
      textarea.style.height = 'auto';
      textarea.style.height = `${Math.min(textarea.scrollHeight, 120)}px`;
    }
  };

  const handleSend = async (generatePlan: boolean) => {
    const trimmed = text.trim();
    if (!trimmed || disabled || isLoading) return;

    // Show user's message immediately
    addMessage({ role: 'user', content: trimmed });
    setThinking(true);

    setText(''); // Clear after adding message
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    try {
      await sendMessage(trimmed, generatePlan);
    } catch {
      // Error handled by useChat
    } finally {
      setThinking(false);
    }
  };

  const handleVoiceToggle = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  return (
    <div className="flex flex-col gap-2 p-4 border-t bg-background">
      {/* Main input row */}
      <div className="flex items-center gap-2">
        {/* Voice input button — only show if supported */}
        {voiceAvailable && (
          <VoiceButton
            isListening={isListening}
            onToggle={handleVoiceToggle}
            disabled={disabled || isLoading}
          />
        )}

        {/* Text input */}
        <textarea
          ref={textareaRef}
          className="flex-1 min-h-[36px] max-h-[120px] h-auto rounded-md border border-input bg-background px-3 py-2 text-sm shadow-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50 resize-none"
          placeholder="Message GoGoGo... (Shift+Enter for new line)"
          value={text}
          onChange={e => {
            setText(e.target.value);
            adjustTextareaHeight();
          }}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend(false);
            }
          }}
          disabled={disabled || isLoading}
          rows={1}
        />

        {/* Send button — simple chat */}
        <Button
          size="lg"
          variant="secondary"
          onClick={() => handleSend(false)}
          disabled={!text.trim() || disabled || isLoading}
          aria-label="Send message"
        >
          <Send className="size-4" />
        </Button>

        {/* Generate Trip Plan button */}
        <Button
          size="lg"
          variant="default"
          onClick={() => handleSend(true)}
          disabled={!text.trim() || disabled || isLoading}
          className="gap-1.5"
          aria-label="Generate full trip plan"
        >
          <Map className="size-3.5" />
          Generate Trip Plan
        </Button>
      </div>
    </div>
  );
}
