// useChat — wire VoiceButton → chatService → POST /chat
// Handles ChatResponse (text + itinerary + message_type)

import { useCallback, useRef } from 'react';
import { chatService, ChatRequest, guestPreferences } from '@/services/api';
import { useChatStore } from '@/store';

interface UseChatOptions {
  onItinerary?: (itinerary: unknown) => void;
  onError?: (error: string) => void;
}

export function useChat({ onItinerary, onError }: UseChatOptions = {}) {
  const { sessionId, addMessage, setSessionId, setLoading } = useChatStore();

  const sendMessage = useCallback(
    async (message: string, generatePlan = false, tripParams?: ChatRequest['trip_parameters']) => {
      console.log('[useChat] sendMessage called', {
        message: message.substring(0, 50),
        generatePlan,
      });
      setLoading(true);
      try {
        // Use guest_uid from localStorage for unauthenticated users
        const guestUid = localStorage.getItem('guest_uid');
        const effectiveSessionId = sessionId ?? guestUid ?? undefined;
        console.log(
          '[useChat] sessionId:',
          sessionId,
          'guestUid:',
          guestUid,
          'effectiveSessionId:',
          effectiveSessionId
        );

        // Always include preferences: guest preferences from localStorage
        // (for logged-in users, the backend fetches from DB via the token)
        const isLoggedIn = !!localStorage.getItem('token');
        const prefs = isLoggedIn ? undefined : guestPreferences.get();
        console.log('[useChat] isLoggedIn:', isLoggedIn, 'prefs:', prefs);

        const req: ChatRequest = {
          message,
          session_id: effectiveSessionId,
          generate_plan: generatePlan,
          trip_parameters: tripParams,
          user_preferences: prefs as unknown as Record<string, unknown>,
        };

        // Use streaming for casual chat (generatePlan=false)
        if (!generatePlan) {
          let fullText = '';
          let chunkCount = 0;

          // Add empty assistant message and get its ID
          const msgId = addMessage({ role: 'assistant', content: '' });
          console.log('[useChat] Added empty assistant message, id:', msgId);

          try {
            for await (const chunk of chatService.streamMessage(req)) {
              chunkCount++;
              fullText += chunk;
              console.log(
                '[useChat] Chunk',
                chunkCount,
                ':',
                chunk.substring(0, 100),
                '| fullText length:',
                fullText.length
              );
              // Update the assistant message with accumulated text
              useChatStore.getState().updateStreamingMessage(msgId, fullText);
            }
            console.log(
              '[useChat] Stream complete. Total chunks:',
              chunkCount,
              'final text length:',
              fullText.length
            );

            // Update session ID if returned (streaming doesn't return session_id separately)
            if (sessionId) {
              setSessionId(sessionId);
            }
          } catch (err) {
            const errorMsg = err instanceof Error ? err.message : 'Stream failed';
            console.error('[useChat] Stream error:', errorMsg);
            useChatStore.getState().updateStreamingMessage(msgId, `Error: ${errorMsg}`);
            onError?.(errorMsg);
          }

          return;
        }

        // Non-streaming path for generate_plan requests
        console.log('[useChat] Using non-streaming path for generate_plan');
        const response = await chatService.sendMessage(req);
        console.log(
          '[useChat] Non-streaming response:',
          JSON.stringify(response).substring(0, 200)
        );

        // Update session ID if returned
        if (response.session_id) {
          setSessionId(response.session_id);
        }

        // Add assistant message
        addMessage({
          role: 'assistant',
          content: response.text || JSON.stringify(response.itinerary || ''),
        });

        // If itinerary returned, notify caller
        if (response.itinerary && onItinerary) {
          onItinerary(response.itinerary);
        }

        // If error, notify caller
        if (response.message_type === 'error' && onError) {
          onError(response.text || 'An error occurred');
        }

        return response;
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Request failed';
        console.error('[useChat] Caught error:', message);
        onError?.(message);
        addMessage({ role: 'assistant', content: `Error: ${message}` });
        throw err;
      } finally {
        setLoading(false);
        console.log('[useChat] setLoading(false) called');
      }
    },
    [sessionId, addMessage, setSessionId, setLoading, onItinerary, onError]
  );

  return { sendMessage };
}
