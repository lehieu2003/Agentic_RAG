import { useCallback } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type {
  ChatMessageData,
  QAResponse,
  ReasoningStep,
  SessionSummary,
} from '../types';
import { askQuestion, getSession, listSessions } from '../api/client';
import { parseReasoningStep } from '../utils/reasoning';
import { clearStoredSessionId, mapSessionMessages, storeSessionId } from '../utils/sessionMessages';

interface ChatActionsParams {
  topK: number;
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
 */
export function useChatActions({
  topK,
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

      try {
        const res: QAResponse = await askQuestion(trimmed, topK, currentSessionId);
        const reasoningSteps: ReasoningStep[] | undefined = Array.isArray(res.reasoning_steps)
          ? res.reasoning_steps.map(parseReasoningStep)
          : undefined;

        const assistantMsg: ChatMessageData = {
          id: `assistant-${Date.now()}-${Math.random()}`,
          role: 'assistant',
          content: res.answer,
          citations: res.citations,
          evidence: res.evidence,
          reasoning_steps: reasoningSteps,
          standalone_question: res.standalone_question,
          timestamp: Date.now(),
        };

        setMessages((prev) => [...prev, assistantMsg]);

        if (res.session_id) {
          setCurrentSessionId(res.session_id);
          storeSessionId(res.session_id);
        }

        try {
          const updatedSessions = await listSessions();
          setSessions(updatedSessions);
        } catch {
          // Ignore background refresh errors
        }
      } catch (err: any) {
        const errorMsg: ChatMessageData = {
          id: `error-${Date.now()}-${Math.random()}`,
          role: 'assistant',
          content: `⚠️ Không thể nhận phản hồi từ hệ thống: ${err.message || 'Lỗi kết nối máy chủ'}. Vui lòng thử lại.`,
          isError: true,
          timestamp: Date.now(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setIsQuerying(false);
      }
    },
    [
      topK,
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
