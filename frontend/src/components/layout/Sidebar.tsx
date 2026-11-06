import React, { useState } from 'react';
import { X } from 'lucide-react';
import type { FileInfo, SessionSummary } from '../../types';
import ChatsPanel from './sidebar/ChatsPanel';
import DocumentsPanel from './sidebar/DocumentsPanel';
import SidebarErrorBanner from './sidebar/SidebarErrorBanner';
import SidebarTabs from './sidebar/SidebarTabs';

export interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  files: FileInfo[];
  onNewChat: () => void;
  onFileUpload: (file: File) => Promise<void>;
  onDeleteFile: (filename: string) => Promise<void>;
  sessions?: SessionSummary[];
  activeSessionId?: string | null;
  onSelectSession?: (id: string) => void;
  onDeleteSession?: (id: string) => Promise<void>;
  onDeleteAllSessions?: () => Promise<void> | void;
  onDeleteSessions?: (sessionIds: string[]) => Promise<void> | void;
  isUploading?: boolean;
  errorMessage?: string | null;
  onDismissError?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onClose,
  files,
  onNewChat,
  onFileUpload,
  onDeleteFile,
  sessions = [],
  activeSessionId = null,
  onSelectSession,
  onDeleteSession,
  onDeleteAllSessions,
  onDeleteSessions,
  isUploading = false,
  errorMessage,
  onDismissError,
}) => {
  const [activeTab, setActiveTab] = useState<'chats' | 'documents'>('chats');
  const [localError, setLocalError] = useState<string | null>(null);

  if (!isOpen) {
    return null;
  }

  const currentError = errorMessage || localError;

  const handleDismissError = () => {
    setLocalError(null);
    onDismissError?.();
  };

  return (
    <>
      {/* Mobile backdrop */}
      <div
        className="fixed inset-0 bg-black/60 backdrop-blur-xs z-30 md:hidden"
        onClick={onClose}
        aria-hidden="true"
      />

      <aside className="fixed inset-y-0 left-0 z-40 md:relative md:z-0 flex flex-col w-72 sm:w-80 h-full bg-zinc-950/95 md:bg-zinc-950/80 backdrop-blur-md border-r border-white/[0.08] text-zinc-300 select-none shrink-0">
        {/* Mobile Header */}
        <div className="flex items-center justify-between px-3 pt-3 pb-1 md:hidden shrink-0">
          <span className="text-xs font-semibold text-zinc-300 tracking-wide uppercase">
            Bảng điều khiển
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close sidebar"
            className="p-1 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <SidebarTabs activeTab={activeTab} onChange={setActiveTab} />

        {currentError && (
          <SidebarErrorBanner message={currentError} onDismiss={handleDismissError} />
        )}

        <ChatsPanel
          isActive={activeTab === 'chats'}
          onNewChat={onNewChat}
          sessions={sessions}
          activeSessionId={activeSessionId}
          onSelectSession={onSelectSession}
          onDeleteSession={onDeleteSession}
          onDeleteAllSessions={onDeleteAllSessions}
          onDeleteSessions={onDeleteSessions}
        />

        <DocumentsPanel
          isActive={activeTab === 'documents'}
          files={files}
          onFileUpload={onFileUpload}
          onDeleteFile={onDeleteFile}
          isUploading={isUploading}
          onLocalError={setLocalError}
          onDismissError={onDismissError}
        />
      </aside>
    </>
  );
};

export default Sidebar;
