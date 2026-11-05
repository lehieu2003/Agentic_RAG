import { useEffect } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type {
  ChatMessageData,
  FileInfo,
  HealthResponse,
  SessionSummary,
} from '../types';
import { checkHealth, getFiles, getSession, listSessions } from '../api/client';
import {
  ACTIVE_SESSION_STORAGE_KEY,
  LEGACY_SESSION_STORAGE_KEY,
  getStoredSessionId,
  mapSessionMessages,
} from '../utils/sessionMessages';

interface InitialWorkspaceDataParams {
  setHealth: Dispatch<SetStateAction<HealthResponse | null>>;
  setFiles: Dispatch<SetStateAction<FileInfo[]>>;
  setSessions: Dispatch<SetStateAction<SessionSummary[]>>;
  setCurrentSessionId: Dispatch<SetStateAction<string | null>>;
  setMessages: Dispatch<SetStateAction<ChatMessageData[]>>;
}

/**
 * Load health, indexed files, chat sessions and the persisted active session on
 * mount. Mirrors the previous inline App effect, including the "don't clobber an
 * in-progress chat" guard when restoring the saved session.
 */
export function useInitialWorkspaceData({
  setHealth,
  setFiles,
  setSessions,
  setCurrentSessionId,
  setMessages,
}: InitialWorkspaceDataParams): void {
  useEffect(() => {
    let mounted = true;

    async function loadInitialData() {
      // Synchronously capture saved session id on mount before any concurrent user interactions
      const savedSessionId = getStoredSessionId();

      try {
        const [healthRes, filesRes, sessionsRes, sessionDetailRes] = await Promise.allSettled([
          checkHealth(),
          getFiles(),
          listSessions(),
          savedSessionId ? getSession(savedSessionId) : Promise.resolve(null),
        ]);

        if (!mounted) return;

        if (healthRes.status === 'fulfilled') {
          setHealth(healthRes.value);
        } else {
          setHealth({ status: 'error' });
        }

        if (filesRes.status === 'fulfilled') {
          setFiles(filesRes.value);
        }

        if (sessionsRes.status === 'fulfilled') {
          setSessions(sessionsRes.value);
        }

        if (savedSessionId) {
          if (
            sessionDetailRes.status === 'fulfilled' &&
            sessionDetailRes.value &&
            'messages' in sessionDetailRes.value &&
            Array.isArray(sessionDetailRes.value.messages)
          ) {
            setCurrentSessionId(savedSessionId);
            const loadedMessages = mapSessionMessages(
              sessionDetailRes.value.messages,
              savedSessionId
            );
            // Don't overwrite if user has already started chatting while initial data was fetching
            setMessages((prev) => (prev.length > 0 ? prev : loadedMessages));
          } else if (sessionDetailRes.status === 'rejected') {
            console.warn('Could not restore saved session:', sessionDetailRes.reason);
            localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
            localStorage.removeItem(LEGACY_SESSION_STORAGE_KEY);
            setCurrentSessionId(null);
          }
        }
      } catch {
        if (mounted) {
          setHealth({ status: 'error' });
        }
      }
    }

    loadInitialData();
    return () => {
      mounted = false;
    };
  }, [setHealth, setFiles, setSessions, setCurrentSessionId, setMessages]);
}
