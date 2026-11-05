import { useCallback, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import type { HealthResponse, ChatMessageData, FileInfo, SessionSummary } from '../types';
import { checkHealth, getFiles, listSessions } from '../api/client';
import type { ActiveDocument } from '../components/viewer/DocumentViewer';
import { useChatActions } from './useChatActions';
import { useDocumentActions } from './useDocumentActions';
import { useInitialWorkspaceData } from './useInitialWorkspaceData';
import { useSessionActions } from './useSessionActions';

export interface Workspace {
  health: HealthResponse | null;
  files: FileInfo[];
  sessions: SessionSummary[];
  currentSessionId: string | null;
  topK: number;
  setTopK: Dispatch<SetStateAction<number>>;
  isSidebarOpen: boolean;
  setIsSidebarOpen: Dispatch<SetStateAction<boolean>>;
  isViewerOpen: boolean;
  setIsViewerOpen: Dispatch<SetStateAction<boolean>>;
  activeDocument: ActiveDocument | null;
  setActiveDocument: Dispatch<SetStateAction<ActiveDocument | null>>;
  messages: ChatMessageData[];
  isQuerying: boolean;
  isUploading: boolean;
  sidebarError: string | null;
  setSidebarError: Dispatch<SetStateAction<string | null>>;
  handleFileUpload: (file: File) => Promise<void>;
  handleDeleteFile: (filename: string) => Promise<void>;
  handleSendMessage: (question: string) => Promise<void>;
  handleRetry: () => void;
  handleCitationClick: (filename: string, page?: number) => void;
  handleNewChat: () => void;
  handleSelectSession: (sessionId: string) => Promise<void>;
  handleDeleteSession: (sessionId: string) => Promise<void>;
  handleDeleteAllSessions: () => Promise<void>;
  handleDeleteSessions: (sessionIds: string[]) => Promise<void>;
}

/**
 * Owns all workspace state and wires the domain action hooks together. The
 * component tree only needs the returned values, which keeps ``App`` focused on
 * layout instead of state management.
 */
export function useWorkspace(): Workspace {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [topK, setTopK] = useState<number>(8);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);
  const [isViewerOpen, setIsViewerOpen] = useState<boolean>(false);
  const [activeDocument, setActiveDocument] = useState<ActiveDocument | null>(null);
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [isQuerying, setIsQuerying] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [sidebarError, setSidebarError] = useState<string | null>(null);
  const [lastQuestion, setLastQuestion] = useState<string>('');

  const refreshState = useCallback(async () => {
    try {
      const [healthData, filesData, sessionsData] = await Promise.allSettled([
        checkHealth(),
        getFiles(),
        listSessions(),
      ]);
      if (healthData.status === 'fulfilled') {
        setHealth(healthData.value);
      }
      if (filesData.status === 'fulfilled') {
        setFiles(filesData.value);
      }
      if (sessionsData.status === 'fulfilled') {
        setSessions(sessionsData.value);
      }
    } catch {
      // Ignore background refresh errors
    }
  }, []);

  const { handleSendMessage, handleRetry, handleNewChat, handleSelectSession } = useChatActions({
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
  });

  const { handleFileUpload, handleDeleteFile } = useDocumentActions({
    activeDocument,
    setActiveDocument,
    setIsUploading,
    setSidebarError,
    refreshState,
  });

  const { handleDeleteSession, handleDeleteAllSessions, handleDeleteSessions } = useSessionActions({
    currentSessionId,
    setSessions,
    setSidebarError,
    onActiveSessionDeleted: handleNewChat,
  });

  useInitialWorkspaceData({
    setHealth,
    setFiles,
    setSessions,
    setCurrentSessionId,
    setMessages,
  });

  const handleCitationClick = useCallback((filename: string, page?: number) => {
    setActiveDocument({ filename, page });
    setIsViewerOpen(true);
  }, []);

  return {
    health,
    files,
    sessions,
    currentSessionId,
    topK,
    setTopK,
    isSidebarOpen,
    setIsSidebarOpen,
    isViewerOpen,
    setIsViewerOpen,
    activeDocument,
    setActiveDocument,
    messages,
    isQuerying,
    isUploading,
    sidebarError,
    setSidebarError,
    handleFileUpload,
    handleDeleteFile,
    handleSendMessage,
    handleRetry,
    handleCitationClick,
    handleNewChat,
    handleSelectSession,
    handleDeleteSession,
    handleDeleteAllSessions,
    handleDeleteSessions,
  };
}
