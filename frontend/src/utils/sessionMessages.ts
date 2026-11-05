import type { ChatMessageData, SessionDetailResponse } from '../types';
import { parseReasoningStep } from './reasoning';

export const ACTIVE_SESSION_STORAGE_KEY = 'doc_qa_active_session_id';
export const LEGACY_SESSION_STORAGE_KEY = 'active_session_id';

/**
 * Map API session messages into the chat message model used by the UI.
 */
export function mapSessionMessages(
  messages: SessionDetailResponse['messages'],
  sessionId: string
): ChatMessageData[] {
  return (messages || []).map((m, idx) => ({
    id: m.id || `msg-${sessionId}-${idx}`,
    role: m.role,
    content: m.content,
    citations: m.citations,
    reasoning_steps: Array.isArray(m.reasoning_steps)
      ? m.reasoning_steps.map(parseReasoningStep)
      : undefined,
    standalone_question: m.standalone_question,
    timestamp: m.created_at ? new Date(m.created_at).getTime() : Date.now(),
  }));
}

/** Read the persisted active session id, falling back to the legacy key. */
export function getStoredSessionId(): string | null {
  return (
    localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY) ||
    localStorage.getItem(LEGACY_SESSION_STORAGE_KEY)
  );
}

/** Persist the active session id for reload restoration. */
export function storeSessionId(sessionId: string): void {
  localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, sessionId);
}

/** Remove the persisted active session id (both current and legacy keys). */
export function clearStoredSessionId(): void {
  localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
  localStorage.removeItem(LEGACY_SESSION_STORAGE_KEY);
}
