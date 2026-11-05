import { useCallback } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { SessionSummary } from '../types';
import { deleteAllSessions, deleteSession, deleteSessionsBatch, listSessions } from '../api/client';

interface SessionActionsParams {
  currentSessionId: string | null;
  setSessions: Dispatch<SetStateAction<SessionSummary[]>>;
  setSidebarError: Dispatch<SetStateAction<string | null>>;
  onActiveSessionDeleted: () => void;
}

export interface SessionActions {
  handleDeleteSession: (sessionId: string) => Promise<void>;
  handleDeleteAllSessions: () => Promise<void>;
  handleDeleteSessions: (sessionIds: string[]) => Promise<void>;
}

/**
 * Session deletion actions (single, all, batch). When the active session is
 * removed, the chat is reset through ``onActiveSessionDeleted``.
 */
export function useSessionActions({
  currentSessionId,
  setSessions,
  setSidebarError,
  onActiveSessionDeleted,
}: SessionActionsParams): SessionActions {
  const handleDeleteSession = useCallback(
    async (sessionId: string) => {
      setSidebarError(null);
      try {
        await deleteSession(sessionId);
        if (currentSessionId === sessionId) {
          onActiveSessionDeleted();
        }
        const updatedSessions = await listSessions();
        setSessions(updatedSessions);
      } catch (err: any) {
        console.error('Failed to delete session:', err);
        const msg = err.response?.data?.detail || err.message || 'Không thể xóa cuộc trò chuyện.';
        setSidebarError(`Lỗi xóa cuộc trò chuyện: ${msg}`);
      }
    },
    [currentSessionId, onActiveSessionDeleted, setSessions, setSidebarError]
  );

  const handleDeleteAllSessions = useCallback(async () => {
    setSidebarError(null);
    try {
      await deleteAllSessions();
      onActiveSessionDeleted();
      setSessions([]);
    } catch (err: any) {
      console.error('Failed to delete all sessions:', err);
      const msg = err.response?.data?.detail || err.message || 'Không thể xóa tất cả cuộc trò chuyện.';
      setSidebarError(`Lỗi xóa tất cả cuộc trò chuyện: ${msg}`);
    }
  }, [onActiveSessionDeleted, setSessions, setSidebarError]);

  const handleDeleteSessions = useCallback(
    async (sessionIds: string[]) => {
      if (!sessionIds.length) return;
      setSidebarError(null);
      try {
        await deleteSessionsBatch(sessionIds);
        if (currentSessionId && sessionIds.includes(currentSessionId)) {
          onActiveSessionDeleted();
        }
        const updatedSessions = await listSessions();
        setSessions(updatedSessions);
      } catch (err: any) {
        console.error('Failed to batch delete sessions:', err);
        const msg = err.response?.data?.detail || err.message || 'Không thể xóa các cuộc trò chuyện đã chọn.';
        setSidebarError(`Lỗi xóa cuộc trò chuyện đã chọn: ${msg}`);
      }
    },
    [currentSessionId, onActiveSessionDeleted, setSessions, setSidebarError]
  );

  return { handleDeleteSession, handleDeleteAllSessions, handleDeleteSessions };
}
