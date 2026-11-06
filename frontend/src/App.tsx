import { X } from 'lucide-react';
import Header from './components/layout/Header';
import Sidebar from './components/layout/Sidebar';
import ChatContainer from './components/chat/ChatContainer';
import DocumentViewer from './components/viewer/DocumentViewer';
import { useWorkspace } from './hooks/useWorkspace';

export default function App() {
  const {
    health,
    files,
    sessions,
    currentSessionId,
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
  } = useWorkspace();

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
          onNewChat={handleNewChat}
          onFileUpload={handleFileUpload}
          onDeleteFile={handleDeleteFile}
          sessions={sessions}
          activeSessionId={currentSessionId}
          onSelectSession={handleSelectSession}
          onDeleteSession={handleDeleteSession}
          onDeleteAllSessions={handleDeleteAllSessions}
          onDeleteSessions={handleDeleteSessions}
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
