// VoiceButton — Mic toggle with pulsing animation when listening
// Only rendered if isVoiceSupported()

import { Mic, MicOff } from "lucide-react";
import { Button } from "@/components/ui/button";

interface VoiceButtonProps {
  isListening: boolean;
  onToggle: () => void;
  disabled?: boolean;
}

export function VoiceButton({ isListening, onToggle, disabled }: VoiceButtonProps) {
  return (
    <div className="relative">
      {/* Pulsing ring when listening */}
      {isListening && (
        <span className="absolute inset-0 flex items-center justify-center">
          <span className="absolute size-8 rounded-full bg-red-400/40 animate-ping" />
          <span className="absolute size-6 rounded-full bg-red-400/30 animate-pulse" />
        </span>
      )}

      <Button
        variant={isListening ? "destructive" : "outline"}
        size="icon"
        onClick={onToggle}
        disabled={disabled}
        aria-label={isListening ? "Stop recording" : "Start recording"}
        className="relative z-10"
      >
        {isListening ? (
          <MicOff className="size-4" />
        ) : (
          <Mic className="size-4" />
        )}
      </Button>
    </div>
  );
}
