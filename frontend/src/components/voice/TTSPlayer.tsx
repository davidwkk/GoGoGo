// TTSPlayer — Auto-play TTS when new assistant message arrives
// If TTS fails, shows text fallback

import { useEffect } from "react";
import { isTTSAvailable, useTTS } from "@/hooks/useTTS";

interface TTSPlayerProps {
  text: string;
  onError?: (error: string) => void;
}

export function TTSPlayer({ text, onError }: TTSPlayerProps) {
  const { speak, stop } = useTTS({
    onError: (e) => onError?.(e),
  });

  useEffect(() => {
    if (!text || !isTTSAvailable()) return;
    speak(text);
    return () => stop();
  }, [text, speak, stop]);

  // If TTS unavailable, caller should show text fallback
  // This component doesn't render anything visible — audio only
  return null;
}
