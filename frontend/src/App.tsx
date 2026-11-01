import { useState, useEffect, useCallback } from 'react';
import type { HealthResponse, FileInfo, ChatMessageData, ReasoningStep } from './types';
import { checkHealth, getFiles, uploadDocument, deleteDocument, askQuestion } from './api/client';
import Header from './components/layout/Header';
import Sidebar from './components/layout/Sidebar';
import ChatContainer from './components/chat/ChatContainer';
import DocumentViewer, { type ActiveDocument } from './components/viewer/DocumentViewer';

export default function App() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [files, setFiles] = useState<FileInfo[]>([]);
  const [topK, setTopK] = useState<number>(8);
  const [isSidebarOpen, setIsSidebarOpen] = useState<boolean>(false);
  const [isViewerOpen, setIsViewerOpen] = useState<boolean>(false);
  const [activeDocument, setActiveDocument] = useState<ActiveDocument | null>(null);
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [isQuerying, setIsQuerying] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [lastQuestion, setLastQuestion] = useState<string>('');

  // Initial load: check health and indexed files
  useEffect(() => {
    let mounted = true;

    async function loadInitialData() {
      try {
        const [healthRes, filesRes] = await Promise.allSettled([
          checkHealth(),
          getFiles(),
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
      const [healthData, filesData] = await Promise.allSettled([
        checkHealth(),
        getFiles(),
      ]);
      if (healthData.status === 'fulfilled') {
        setHealth(healthData.value);
      }
      if (filesData.status === 'fulfilled') {
        setFiles(filesData.value);
      }
    } catch {
      // Ignore background refresh errors
    }
  }, []);

  const handleFileUpload = async (file: File) => {
    try {
      setIsUploading(true);
      await uploadDocument(file);
      await refreshState();
    } catch (err: any) {
      console.error('File upload error:', err);
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeleteFile = async (filename: string) => {
    try {
      await deleteDocument(filename);
      if (activeDocument?.filename === filename) {
        setActiveDocument(null);
      }
      await refreshState();
    } catch (err: any) {
      console.error('File delete error:', err);
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
      const res = await askQuestion(trimmed, topK);
      const reasoningSteps: ReasoningStep[] | undefined = Array.isArray(res.reasoning_steps)
        ? (res.reasoning_steps.map((s) =>
            typeof s === 'string' ? { node: s, status: 'completed' } : s
          ) as ReasoningStep[])
        : undefined;

      const assistantMsg: ChatMessageData = {
        id: `assistant-${Date.now()}-${Math.random()}`,
        role: 'assistant',
        content: res.answer,
        citations: res.citations,
        evidence: res.evidence,
        reasoning_steps: reasoningSteps,
        timestamp: Date.now(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
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
    setMessages([]);
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-obsidian-bg text-obsidian-text overflow-hidden">
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
          isUploading={isUploading}
        />

        {/* Workspace Split Panes */}
        <main className="flex-1 flex min-w-0 overflow-hidden relative">
          {/* Left Pane: Chat Assistant */}
          <div
            className={`flex flex-col h-full min-w-0 transition-all duration-300 ${
              isViewerOpen ? 'w-full md:w-[60%]' : 'w-full'
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
            <div className="w-full md:w-[40%] h-full shrink-0 min-w-0">
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
