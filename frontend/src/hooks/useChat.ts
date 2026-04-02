// useChat — wire VoiceButton → chatService → POST /chat
// Handles ChatResponse (text + itinerary + message_type)

import { useCallback } from 'react';
import { chatService, ChatRequest, guestPreferences } from '@/services/api';
import { useChatStore } from '@/store';
import type { TripItinerary } from '@/types/trip';

// Map raw tool names to user-friendly display labels
const TOOL_LABELS: Record<string, string> = {
  get_attraction: 'Getting attraction info',
  get_weather: 'Getting weather',
  search_web: 'Searching the web',
  search_flights: 'Searching flights',
  search_hotels: 'Searching hotels',
  get_transport: 'Getting transport info',
  build_embed_url: 'Building map',
  build_static_url: 'Building map',
};

function formatThinkingStep(raw: string): string {
  const s = raw.trim();

  if (s === 'thinking') return '💭 Thinking...';
  if (s === 'processing_results') return '📊 Processing results...';

  if (s.startsWith('calling_')) {
    const tool = s.slice('calling_'.length);
    const label = TOOL_LABELS[tool] ?? tool.replace(/_/g, ' ');
    return `🔍 ${label}...`;
  }

  // Tool result
  const label = TOOL_LABELS[s] ?? s.replace(/_/g, ' ');
  return `✅ ${label}`;
}

interface UseChatOptions {
  onItinerary?: (itinerary: TripItinerary) => void;
  onError?: (error: string) => void;
}

export function useChat({ onItinerary, onError }: UseChatOptions = {}) {
  const {
    sessionId,
    addMessage,
    setSessionId,
    forceNewSessionNextMessage,
    setForceNewSessionNextMessage,
    setLoading,
    setAbortController,
    setThinking,
    addThinkingStep,
    setPartialThoughtText,
  } = useChatStore();

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
        const isLoggedIn = !!localStorage.getItem('access_token');
        const prefs = isLoggedIn ? undefined : guestPreferences.get();
        console.log('[useChat] isLoggedIn:', isLoggedIn, 'prefs:', prefs);

        const req: ChatRequest = {
          message,
          session_id: effectiveSessionId,
          force_new_session: forceNewSessionNextMessage || undefined,
          generate_plan: generatePlan,
          trip_parameters: tripParams,
          user_preferences: prefs as unknown as Record<string, unknown>,
        };
        if (forceNewSessionNextMessage) setForceNewSessionNextMessage(false);

        // Use streaming for casual chat (generatePlan=false)
        if (!generatePlan) {
          let fullText = '';
          let chunkCount = 0;
          let msgId: string | null = null;

          // Create abort controller for this stream
          const abortController = new AbortController();
          setAbortController(abortController);
          setThinking(true);

          try {
            for await (const chunk of chatService.streamMessage(req, abortController.signal)) {
              // Handle special prefixed events from agent thought streaming
              if (typeof chunk === 'string') {
                if (chunk.startsWith('__ERROR__:')) {
                  const errorMsg = chunk.slice('__ERROR__:'.length);
                  setThinking(false);
                  if (msgId !== null) {
                    useChatStore
                      .getState()
                      .updateStreamingMessage(msgId, `Error: ${errorMsg}`, 'error');
                  } else {
                    addMessage({
                      role: 'assistant',
                      content: `Error: ${errorMsg}`,
                      messageType: 'error',
                    });
                  }
                  onError?.(errorMsg);
                  setAbortController(null);
                  return;
                }
                // Commit any pending partial thought before processing a non-thought event
                const commitPartialThought = () => {
                  const partial = useChatStore.getState().partialThoughtText;
                  if (partial) {
                    addThinkingStep(partial);
                    setPartialThoughtText('');
                  }
                };

                if (chunk.startsWith('__THOUGHT__:')) {
                  commitPartialThought();
                  const step = chunk.slice('__THOUGHT__:'.length);
                  addThinkingStep(step);
                  continue;
                }
                if (chunk.startsWith('__MODEL_THOUGHT__:')) {
                  const thought = chunk.slice('__MODEL_THOUGHT__:'.length);
                  const current = useChatStore.getState().partialThoughtText;
                  setPartialThoughtText(current + thought);
                  continue;
                }
                if (chunk.startsWith('__TOOL_CALL__:')) {
                  commitPartialThought();
                  const toolName = chunk.slice('__TOOL_CALL__:'.length);
                  addThinkingStep(formatThinkingStep(`calling_${toolName}`));
                  continue;
                }
                if (chunk.startsWith('__TOOL_RESULT__:')) {
                  commitPartialThought();
                  const toolName = chunk.slice('__TOOL_RESULT__:'.length);
                  addThinkingStep(formatThinkingStep(toolName));
                  continue;
                }
                if (chunk.startsWith('__STATUS__:')) {
                  commitPartialThought();
                  const status = chunk.slice('__STATUS__:'.length);
                  addThinkingStep(formatThinkingStep(status));
                  continue;
                }
              }

              // Commit any pending partial thought before text chunks
              {
                const partial = useChatStore.getState().partialThoughtText;
                if (partial) {
                  addThinkingStep(partial);
                  setPartialThoughtText('');
                }
              }

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
              // On first text chunk, create the assistant message (keep thinking steps visible)
              if (msgId === null) {
                msgId = addMessage({ role: 'assistant', content: chunk });
                setThinking(false);
              } else {
                // Update the assistant message with accumulated text
                useChatStore.getState().updateStreamingMessage(msgId, fullText);
              }
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

            // Commit any remaining partial thought at end of stream
            {
              const partial = useChatStore.getState().partialThoughtText;
              if (partial) {
                addThinkingStep(partial);
                setPartialThoughtText('');
              }
            }
          } catch (err) {
            // Ignore AbortError — user cancelled the stream
            if (err instanceof Error && err.name === 'AbortError') {
              console.log('[useChat] Stream cancelled by user');
              setThinking(false);
              setAbortController(null);
              // Commit any remaining partial thought
              {
                const partial = useChatStore.getState().partialThoughtText;
                if (partial) {
                  addThinkingStep(partial);
                  setPartialThoughtText('');
                }
              }
              return;
            }
            let errorMsg = err instanceof Error ? err.message : 'Stream failed';
            // Make "model high demand" errors more user-friendly
            if (errorMsg.includes('high demand') || errorMsg.includes('503')) {
              errorMsg =
                'The AI is experiencing high demand right now. Please try again in a few moments.';
            }
            console.error('[useChat] Stream error:', errorMsg);
            setThinking(false);
            // Commit any remaining partial thought
            {
              const partial = useChatStore.getState().partialThoughtText;
              if (partial) {
                addThinkingStep(partial);
                setPartialThoughtText('');
              }
            }
            // If we already have a message, update it; otherwise create one with the error
            if (msgId !== null) {
              useChatStore.getState().updateStreamingMessage(msgId, `Error: ${errorMsg}`);
            } else {
              addMessage({ role: 'assistant', content: `Error: ${errorMsg}` });
            }
            onError?.(errorMsg);
          } finally {
            setThinking(false);
            setAbortController(null);
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
          onItinerary(response.itinerary as TripItinerary);
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
    [
      sessionId,
      addMessage,
      setSessionId,
      forceNewSessionNextMessage,
      setForceNewSessionNextMessage,
      setLoading,
      setAbortController,
      setThinking,
      onItinerary,
      onError,
    ]
  );

  return { sendMessage };
}
