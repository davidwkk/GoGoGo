// InputBar — Text input + Send + Generate Trip Plan + Voice input
// Wired to useChat hook; voice button uses ASR to populate input field.

import { useState } from "react";
import { Send, Map } from "lucide-react";

import { Button } from "@/components/ui/button";
import { VoiceButton } from "@/components/voice/VoiceButton";
import { useChat } from "@/hooks/useChat";
import { useASR } from "@/hooks/useASR";
import { useChatStore } from "@/store";

interface InputBarProps {
  disabled?: boolean;
}

export function InputBar({ disabled }: InputBarProps) {
  const [text, setText] = useState("");
  const voiceAvailable = useChatStore((s) => s.voiceAvailable);
  const isLoading = useChatStore((s) => s.isLoading);
  const { sendMessage } = useChat({});
  const { isListening, startListening, stopListening } = useASR({
    onTranscript: (result) => {
      // Append transcript to existing text (allows multiple utterances)
      setText((prev) => {
        const next = prev ? `${prev} ${result.transcript}` : result.transcript;
        return next;
      });
    },
    onError: (error) => {
      console.warn("ASR error:", error);
    },
  });

  const handleSend = async (generatePlan: boolean) => {
    const trimmed = text.trim();
    if (!trimmed || disabled || isLoading) return;
    setText(""); // Clear before sending for better UX
    try {
      await sendMessage(trimmed, generatePlan);
    } catch {
      // Error handled by useChat
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
        <input
          type="text"
          className="flex-1 h-9 rounded-md border border-input bg-background px-3 text-sm shadow-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
          placeholder="Message GoGoGo..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSend(false);
            }
          }}
          disabled={disabled || isLoading}
        />

        {/* Send button — simple chat */}
        <Button
          size="sm"
          variant="secondary"
          onClick={() => handleSend(false)}
          disabled={!text.trim() || disabled || isLoading}
          aria-label="Send message"
        >
          <Send className="size-4" />
        </Button>
      </div>

      {/* Generate Trip Plan row */}
      <div className="flex justify-end">
        <Button
          size="sm"
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
