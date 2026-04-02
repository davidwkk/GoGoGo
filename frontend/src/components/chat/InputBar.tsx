// InputBar — Text input + Send + Voice input
// Wired to useChat hook; voice button uses ASR to populate input field.

import { useLayoutEffect, useRef, useState } from 'react';
import { Send } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { VoiceButton } from '@/components/voice/VoiceButton';
import { useChat } from '@/hooks/useChat';
import { useASR } from '@/hooks/useASR';
import { useChatStore } from '@/store';
import { type TripItinerary } from '@/types/trip';

interface InputBarProps {
  disabled?: boolean;
  onItinerary?: (itinerary: TripItinerary) => void;
}

/** Max height before the input scrolls (~10rem); grows from one line up to this. */
const TEXTAREA_MAX_HEIGHT_PX = 160;

export function InputBar({ disabled, onItinerary }: InputBarProps) {
  const [text, setText] = useState('');
  /** Text in the field when mic was turned on — voice replaces only the new utterance, not appended per interim chunk. */
  const textWhenVoiceStartedRef = useRef('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useLayoutEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = '0px';
    el.style.height = `${Math.min(el.scrollHeight, TEXTAREA_MAX_HEIGHT_PX)}px`;
  }, [text]);
  const voiceAvailable = useChatStore(s => s.voiceAvailable);
  const isLoading = useChatStore(s => s.isLoading);
  const addMessage = useChatStore(s => s.addMessage);
  const setThinking = useChatStore(s => s.setThinking);
  const travelSettings = useChatStore(s => s.travelSettings);
  const { sendMessage } = useChat({ onItinerary });
  const { isListening, startListening, stopListening } = useASR({
    onTranscript: result => {
      const base = textWhenVoiceStartedRef.current.trimEnd();
      const piece = result.transcript.trim();
      if (!piece) return;
      const sep = base ? ' ' : '';
      setText(`${base}${sep}${piece}`);
    },
    onError: error => {
      console.warn('ASR error:', error);
    },
  });

  const handleSend = async (generatePlan: boolean) => {
    const trimmed = text.trim();
    if (!trimmed || disabled || isLoading) return;

    // Show user's message immediately
    addMessage({ role: 'user', content: trimmed });
    setThinking(true);

    setText(''); // Clear after adding message
    try {
      // Build trip parameters from travel settings when generating plan
      const tripParams = generatePlan
        ? {
            destination: travelSettings.destination,
            start_date: travelSettings.start_date,
            end_date: travelSettings.end_date,
            group_type: travelSettings.group_type,
            group_size: travelSettings.group_size,
            purpose: travelSettings.purpose,
          }
        : undefined;
      await sendMessage(trimmed, generatePlan, tripParams);
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
      textWhenVoiceStartedRef.current = text;
      startListening();
    }
  };

  return (
    <div className="flex flex-col gap-2 p-4 border-t bg-background">
      {/* Main input row — items-end so actions stay bottom-aligned when the textarea grows */}
      <div className="flex items-end gap-2">
        {/* Voice input button — only show if supported */}
        {voiceAvailable && (
          <VoiceButton
            isListening={isListening}
            onToggle={handleVoiceToggle}
            disabled={disabled || isLoading}
          />
        )}

        {/* Multiline text: wraps at width; grows up to max height then scrolls */}
        <textarea
          ref={textareaRef}
          rows={1}
          className="flex-1 min-h-9 max-h-40 w-full resize-none overflow-y-auto break-words rounded-md border border-input bg-background px-3 py-2 text-sm leading-snug shadow-sm placeholder:text-muted-foreground [field-sizing:fixed] focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50 box-border"
          placeholder="Message GoGoGo..."
          value={text}
          onChange={e => setText(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend(false);
            }
          }}
          disabled={disabled || isLoading}
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
      </div>
    </div>
  );
}
