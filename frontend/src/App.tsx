import { useState, useEffect, useCallback } from 'react';
import { X } from 'lucide-react';
import type {
  HealthResponse,
  FileInfo,
  ChatMessageData,
  ReasoningStep,
  SessionSummary,
} from './types';
import {
  checkHealth,
  getFiles,
  uploadDocument,
  deleteDocument,
  askQuestion,
  listSessions,
  getSession,
  deleteSession,
} from './api/client';
import Header from './components/layout/Header';
import Sidebar from './components/layout/Sidebar';
import ChatContainer from './components/chat/ChatContainer';
import DocumentViewer, { type ActiveDocument } from './components/viewer/DocumentViewer';

const ACTIVE_SESSION_STORAGE_KEY = 'doc_qa_active_session_id';
const LEGACY_SESSION_STORAGE_KEY = 'active_session_id';

export function parseReasoningStep(step: ReasoningStep | string): ReasoningStep {
  if (typeof step !== 'string') {
    return step;
  }
  const match = step.match(/^(\d+\.?\s*[\w_]+):\s*(.*)$/);
  if (match) {
    const cleanNode = match[1].replace(/^\d+\.?\s*/, '').trim();
    return {
      node: cleanNode,
      message: match[2],
      status: 'completed',
    };
  }
  return {
    node: step,
    status: 'completed',
  };
}

export default function App() {
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

  // Initial load: check health, indexed files, and chat sessions
  useEffect(() => {
    let mounted = true;

    async function loadInitialData() {
      // Synchronously capture saved session id on mount before any concurrent user interactions
      const savedSessionId =
        localStorage.getItem(ACTIVE_SESSION_STORAGE_KEY) ||
        localStorage.getItem(LEGACY_SESSION_STORAGE_KEY);

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
            const loadedMessages: ChatMessageData[] = sessionDetailRes.value.messages.map(
              (m, idx) => ({
                id: m.id || `msg-${savedSessionId}-${idx}`,
                role: m.role,
                content: m.content,
                citations: m.citations,
                reasoning_steps: Array.isArray(m.reasoning_steps)
                  ? m.reasoning_steps.map(parseReasoningStep)
                  : undefined,
                standalone_question: m.standalone_question,
                timestamp: m.created_at ? new Date(m.created_at).getTime() : Date.now(),
              })
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
  }, []);

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

  const handleFileUpload = async (file: File) => {
    setSidebarError(null);
    try {
      setIsUploading(true);
      await uploadDocument(file);
      await refreshState();
    } catch (err: any) {
      console.error('File upload error:', err);
      const msg =
        err.response?.data?.detail ||
        err.message ||
        'Tải tệp lên thất bại. Vui lòng kiểm tra định dạng hoặc thử lại.';
      setSidebarError(`Lỗi tải tệp: ${msg}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeleteFile = async (filename: string) => {
    setSidebarError(null);
    try {
      await deleteDocument(filename);
      if (activeDocument?.filename === filename) {
        setActiveDocument(null);
      }
      await refreshState();
    } catch (err: any) {
      console.error('File delete error:', err);
      const msg =
        err.response?.data?.detail ||
        err.message ||
        'Xóa tệp thất bại. Vui lòng thử lại.';
      setSidebarError(`Lỗi xóa tệp: ${msg}`);
    }
  };

  const handleSendMessage = async (question: string) => {
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
      const res = await askQuestion(trimmed, topK, currentSessionId);
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
        localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, res.session_id);
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
  };

  const handleRetry = () => {
    if (lastQuestion) {
      handleSendMessage(lastQuestion);
    }
  };

  const handleCitationClick = (filename: string, page?: number) => {
    setActiveDocument({ filename, page });
    setIsViewerOpen(true);
  };

  const handleNewChat = () => {
    setCurrentSessionId(null);
    localStorage.removeItem(ACTIVE_SESSION_STORAGE_KEY);
    localStorage.removeItem(LEGACY_SESSION_STORAGE_KEY);
    setMessages([]);
  };

  const handleSelectSession = async (sessionId: string) => {
    setSidebarError(null);
    try {
      const sessionDetail = await getSession(sessionId);
      setCurrentSessionId(sessionId);
      localStorage.setItem(ACTIVE_SESSION_STORAGE_KEY, sessionId);

      const loadedMessages: ChatMessageData[] = (sessionDetail.messages || []).map((m, idx) => ({
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
      setMessages(loadedMessages);
    } catch (err: any) {
      console.error('Failed to load session:', err);
      const msg = err.response?.data?.detail || err.message || 'Không thể tải cuộc trò chuyện.';
      setSidebarError(`Lỗi tải cuộc trò chuyện: ${msg}`);
    }
  };

  const handleDeleteSession = async (sessionId: string) => {
    setSidebarError(null);
    try {
      await deleteSession(sessionId);
      if (currentSessionId === sessionId) {
        handleNewChat();
      }
      const updatedSessions = await listSessions();
      setSessions(updatedSessions);
    } catch (err: any) {
      console.error('Failed to delete session:', err);
      const msg = err.response?.data?.detail || err.message || 'Không thể xóa cuộc trò chuyện.';
      setSidebarError(`Lỗi xóa cuộc trò chuyện: ${msg}`);
    }
  };

  return (
    <div className="min-h-screen h-screen w-screen bg-canvas text-zinc-200 flex flex-col font-sans selection:bg-sky-500/30 selection:text-white overflow-hidden">
      {/* App Header */}
      <Header
        isViewerOpen={isViewerOpen}
        onToggleViewer={() => setIsViewerOpen((prev) => !prev)}
        isSidebarOpen={isSidebarOpen}
        onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
        health={health}
      />

      {/* Main Workspace Body */}
      <div className="flex-1 flex min-h-0 overflow-hidden relative">
        {/* Left Sidebar */}
        <Sidebar
          isOpen={isSidebarOpen}
          onClose={() => setIsSidebarOpen(false)}
          files={files}
          topK={topK}
          onTopKChange={setTopK}
          onNewChat={handleNewChat}
          onFileUpload={handleFileUpload}
          onDeleteFile={handleDeleteFile}
          sessions={sessions}
          activeSessionId={currentSessionId}
          onSelectSession={handleSelectSession}
          onDeleteSession={handleDeleteSession}
          isUploading={isUploading}
          errorMessage={sidebarError}
          onDismissError={() => setSidebarError(null)}
        />

        {/* Workspace Split Panes */}
        <main className="flex-1 flex flex-col md:flex-row min-w-0 overflow-hidden relative">
          {sidebarError && !isSidebarOpen && (
            <div
              role="alert"
              className="absolute top-3 left-1/2 -translate-x-1/2 z-20 max-w-md w-11/12 px-4 py-2.5 bg-rose-950/90 border border-rose-500/40 backdrop-blur-md shadow-2xl rounded-xl text-rose-200 text-xs flex items-center justify-between"
            >
              <span className="truncate pr-2">{sidebarError}</span>
              <button
                type="button"
                onClick={() => setSidebarError(null)}
                aria-label="Dismiss error banner"
                className="text-rose-400 hover:text-white p-1 rounded-lg hover:bg-white/[0.06] shrink-0 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {/* Left Pane: Chat Assistant */}
          <div
            className={`flex flex-col h-full min-w-0 transition-all duration-300 ${
              isViewerOpen ? 'w-full md:w-[60%] flex-1' : 'w-full'
            }`}
          >
            <ChatContainer
              messages={messages}
              isQuerying={isQuerying}
              onSendMessage={handleSendMessage}
              onCitationClick={handleCitationClick}
              onRetry={handleRetry}
            />
          </div>

          {/* Right Pane: Document Viewer */}
          {isViewerOpen && (
            <div className="w-full md:w-[40%] flex-1 md:flex-initial h-full shrink-0 min-w-0 border-t md:border-t-0 md:border-l border-white/[0.06]">
              <DocumentViewer
                activeDocument={activeDocument}
                onClose={() => setIsViewerOpen(false)}
                onPageChange={(page) => {
                  if (activeDocument) {
                    setActiveDocument({ ...activeDocument, page });
                  }
                }}
                className="w-full"
              />
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
