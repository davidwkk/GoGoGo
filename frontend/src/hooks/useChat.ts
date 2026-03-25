// useChat — wire VoiceButton → chatService → POST /chat
// Handles ChatResponse (text + itinerary + message_type)

import { useCallback } from "react";
import { chatService, ChatRequest } from "@/services/api";
import { useChatStore } from "@/store";

interface UseChatOptions {
  onItinerary?: (itinerary: unknown) => void;
  onError?: (error: string) => void;
}

export function useChat({ onItinerary, onError }: UseChatOptions = {}) {
  const { sessionId, addMessage, setSessionId, setLoading } = useChatStore();

  const sendMessage = useCallback(
    async (
      message: string,
      generatePlan = false,
      tripParams?: ChatRequest["trip_parameters"]
    ) => {
      setLoading(true);
      try {
        const req: ChatRequest = {
          message,
          session_id: sessionId ?? undefined,
          generate_plan: generatePlan,
          trip_parameters: tripParams,
        };

        const response = await chatService.sendMessage(req);

        // Update session ID if returned
        if (response.session_id) {
          setSessionId(response.session_id);
        }

        // Add assistant message
        addMessage({
          role: "assistant",
          content: response.text || JSON.stringify(response.itinerary || ""),
        });

        // If itinerary returned, notify caller
        if (response.itinerary && onItinerary) {
          onItinerary(response.itinerary);
        }

        // If error, notify caller
        if (response.message_type === "error" && onError) {
          onError(response.text || "An error occurred");
        }

        return response;
      } catch (err) {
        const message = err instanceof Error ? err.message : "Request failed";
        onError?.(message);
        addMessage({ role: "assistant", content: `Error: ${message}` });
        throw err;
      } finally {
        setLoading(false);
      }
    },
    [sessionId, addMessage, setSessionId, setLoading, onItinerary, onError]
  );

  return { sendMessage };
}

