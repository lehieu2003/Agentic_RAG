import { useCallback } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type {
  ChatMessageData,
  QAResponse,
  ReasoningStep,
  SessionSummary,
} from '../types';
import { askQuestion, askQuestionStream, getSession, listSessions } from '../api/client';
import { parseReasoningStep } from '../utils/reasoning';
import { clearStoredSessionId, mapSessionMessages, storeSessionId } from '../utils/sessionMessages';

interface ChatActionsParams {
  currentSessionId: string | null;
  isQuerying: boolean;
  lastQuestion: string;
  setMessages: Dispatch<SetStateAction<ChatMessageData[]>>;
  setCurrentSessionId: Dispatch<SetStateAction<string | null>>;
  setIsQuerying: Dispatch<SetStateAction<boolean>>;
  setLastQuestion: Dispatch<SetStateAction<string>>;
  setSessions: Dispatch<SetStateAction<SessionSummary[]>>;
  setSidebarError: Dispatch<SetStateAction<string | null>>;
}

export interface ChatActions {
  handleSendMessage: (question: string) => Promise<void>;
  handleRetry: () => void;
  handleNewChat: () => void;
  handleSelectSession: (sessionId: string) => Promise<void>;
}

/**
 * Chat lifecycle actions: sending questions, retrying, starting a new chat and
 * loading an existing session's history.
 *
 * Questions are asked over the SSE stream: a placeholder assistant message
 * appears as soon as the first reasoning step arrives and is updated live.
 * When streaming is unavailable (older backend, mocked/proxied environments)
 * the hook transparently falls back to the synchronous endpoint.
 */
export function useChatActions({
  currentSessionId,
  isQuerying,
  lastQuestion,
  setMessages,
  setCurrentSessionId,
  setIsQuerying,
  setLastQuestion,
  setSessions,
  setSidebarError,
}: ChatActionsParams): ChatActions {
  const handleSendMessage = useCallback(
    async (question: string) => {
      const trimmed = question.trim();
      if (!trimmed || isQuerying) return;

      const userMsg: ChatMessageData = {
        id: `user-${Date.now()}-${Math.random()}`,
        role: 'user',
        content: trimmed,
        timestamp: Date.now(),
      };

      setMessages((prev) => [...prev, userMsg]);
      setIsQuerying(true);
      setLastQuestion(trimmed);

      const assistantId = `assistant-${Date.now()}-${Math.random()}`;
      let receivedStreamEvent = false;

      // Insert the placeholder on first use, then update it in place.
      const upsertAssistant = (
        updater: (existing: ChatMessageData | undefined) => ChatMessageData,
      ) => {
        setMessages((prev) => {
          const index = prev.findIndex((m) => m.id === assistantId);
          if (index >= 0) {
            const copy = [...prev];
            copy[index] = updater(prev[index]);
            return copy;
          }
          return [...prev, updater(undefined)];
        });
      };

      const applyFinalResponse = (res: QAResponse) => {
        const reasoningSteps: ReasoningStep[] | undefined = Array.isArray(res.reasoning_steps)
          ? res.reasoning_steps.map(parseReasoningStep)
          : undefined;
        upsertAssistant(() => ({
          id: assistantId,
          role: 'assistant',
          content: res.answer,
          citations: res.citations,
          evidence: res.evidence,
          reasoning_steps: reasoningSteps,
          standalone_question: res.standalone_question,
          timestamp: Date.now(),
        }));
        if (res.session_id) {
          setCurrentSessionId(res.session_id);
          storeSessionId(res.session_id);
        }
      };

      const refreshSessions = async () => {
        try {
          const updatedSessions = await listSessions();
          setSessions(updatedSessions);
        } catch {
          // Ignore background refresh errors
        }
      };

      const appendErrorBubble = (message: string) => {
        setMessages((prev) => [
          ...prev,
          {
            id: `error-${Date.now()}-${Math.random()}`,
            role: 'assistant',
            content: message,
            isError: true,
            timestamp: Date.now(),
          },
        ]);
      };

      try {
        const res: QAResponse = await askQuestionStream(trimmed, currentSessionId, {
          onSession: (sessionId) => {
            receivedStreamEvent = true;
            setCurrentSessionId(sessionId);
            storeSessionId(sessionId);
          },
          onStep: (step) => {
            receivedStreamEvent = true;
            upsertAssistant((existing) => ({
              id: assistantId,
              role: 'assistant',
              content: existing?.content ?? '',
              citations: existing?.citations,
              evidence: existing?.evidence,
              reasoning_steps: [...(existing?.reasoning_steps ?? []), parseReasoningStep(step)],
              timestamp: existing?.timestamp ?? Date.now(),
            }));
          },
        });
        applyFinalResponse(res);
        await refreshSessions();
      } catch (err: any) {
        if (receivedStreamEvent) {
          // The stream broke midway: turn the placeholder into an error bubble.
          upsertAssistant((existing) => ({
            id: assistantId,
            role: 'assistant',
            content: `⚠️ ${err.message || 'Lỗi kết nối máy chủ'}. Vui lòng thử lại.`,
            reasoning_steps: existing?.reasoning_steps,
            isError: true,
            timestamp: Date.now(),
          }));
        } else {
          // Streaming unavailable (older backend / mocked environment):
          // fall back to the synchronous endpoint.
          try {
            const res: QAResponse = await askQuestion(trimmed, currentSessionId);
            applyFinalResponse(res);
            await refreshSessions();
          } catch (fallbackErr: any) {
            appendErrorBubble(
              `⚠️ Không thể nhận phản hồi từ hệ thống: ${
                fallbackErr.message || 'Lỗi kết nối máy chủ'
              }. Vui lòng thử lại.`,
            );
          }
        }
      } finally {
        setIsQuerying(false);
      }
    },
    [
      currentSessionId,
      isQuerying,
      setMessages,
      setCurrentSessionId,
      setIsQuerying,
      setLastQuestion,
      setSessions,
    ]
  );

  const handleRetry = useCallback(() => {
    if (lastQuestion) {
      handleSendMessage(lastQuestion);
    }
  }, [lastQuestion, handleSendMessage]);

  const handleNewChat = useCallback(() => {
    setCurrentSessionId(null);
    clearStoredSessionId();
    setMessages([]);
  }, [setCurrentSessionId, setMessages]);

  const handleSelectSession = useCallback(
    async (sessionId: string) => {
      setSidebarError(null);
      try {
        const sessionDetail = await getSession(sessionId);
        setCurrentSessionId(sessionId);
        storeSessionId(sessionId);
        setMessages(mapSessionMessages(sessionDetail.messages, sessionId));
      } catch (err: any) {
        console.error('Failed to load session:', err);
        const msg = err.response?.data?.detail || err.message || 'Không thể tải cuộc trò chuyện.';
        setSidebarError(`Lỗi tải cuộc trò chuyện: ${msg}`);
      }
    },
    [setCurrentSessionId, setMessages, setSidebarError]
  );

  return { handleSendMessage, handleRetry, handleNewChat, handleSelectSession };
}
