import React, { useRef, useState } from 'react';
import {
  Plus,
  Trash2,
  UploadCloud,
  FileText,
  X,
  Loader2,
  Database,
  SlidersHorizontal,
  AlertCircle,
  MessageSquare,
  Files,
  CheckSquare,
} from 'lucide-react';
import type { FileInfo, SessionSummary } from '../../types';

export interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  files: FileInfo[];
  topK: number;
  onTopKChange: (val: number) => void;
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

const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.md', '.png', '.jpg', '.jpeg'];

function isValidFileExtension(fileName: string): boolean {
  const lower = fileName.toLowerCase();
  return ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

function formatFileSize(bytes: number): string {
  if (!bytes || bytes <= 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatSessionDate(dateStr?: string): string {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return '';
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    if (diffMs < 0) return 'Vừa xong';
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    if (diffMins < 1) return 'Vừa xong';
    if (diffMins < 60) return `${diffMins}m trước`;
    if (diffHours < 24) return `${diffHours}h trước`;
    if (diffDays < 7) return `${diffDays}d trước`;
    return d.toLocaleDateString('vi-VN', { month: 'numeric', day: 'numeric' });
  } catch {
    return '';
  }
}

export const Sidebar: React.FC<SidebarProps> = ({
  isOpen,
  onClose,
  files,
  topK,
  onTopKChange,
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
  const [isDragging, setIsDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const [isSelectMode, setIsSelectMode] = useState(false);
  const [selectedSessionIds, setSelectedSessionIds] = useState<Set<string>>(new Set());
  const fileInputRef = useRef<HTMLInputElement>(null);

  const toggleSelectSession = (id: string) => {
    setSelectedSessionIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedSessionIds.size === sessions.length) {
      setSelectedSessionIds(new Set());
    } else {
      setSelectedSessionIds(new Set(sessions.map((s) => s.id)));
    }
  };

  const handleDeleteAllSessions = () => {
    const confirmed = window.confirm(
      'Bạn có chắc chắn muốn xóa tất cả cuộc trò chuyện không?'
    );
    if (confirmed) {
      onDeleteAllSessions?.();
    }
  };

  const handleDeleteSelected = () => {
    const count = selectedSessionIds.size;
    if (count === 0) return;
    const confirmed = window.confirm(
      `Bạn có chắc chắn muốn xóa ${count} cuộc trò chuyện đã chọn không?`
    );
    if (confirmed) {
      onDeleteSessions?.(Array.from(selectedSessionIds));
      setIsSelectMode(false);
      setSelectedSessionIds(new Set());
    }
  };

  if (!isOpen) {
    return null;
  }

  const currentError = errorMessage || localError;

  const handleDismissError = () => {
    setLocalError(null);
    onDismissError?.();
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = async (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (isUploading) return;

    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      if (!isValidFileExtension(droppedFile.name)) {
        setLocalError(
          `Định dạng tệp "${droppedFile.name}" không được hỗ trợ. Vui lòng chọn .pdf, .docx, .txt hoặc .md`
        );
        return;
      }
      setLocalError(null);
      onDismissError?.();
      await onFileUpload(droppedFile);
    }
  };

  const handleFileInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (!isValidFileExtension(selectedFile.name)) {
        setLocalError(
          `Định dạng tệp "${selectedFile.name}" không được hỗ trợ. Vui lòng chọn .pdf, .docx, .txt hoặc .md`
        );
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        return;
      }
      setLocalError(null);
      onDismissError?.();
      await onFileUpload(selectedFile);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDelete = (file: FileInfo) => {
    const confirmed = window.confirm(
      `Bạn có chắc chắn muốn xóa "${file.filename}" khỏi hệ thống không?`
    );
    if (confirmed) {
      onDeleteFile(file.filename);
    }
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

        {/* Segmented Tabs Control */}
        <div
          role="tablist"
          aria-label="Chuyển đổi danh mục"
          className="bg-zinc-900/90 border border-white/[0.08] p-1 rounded-xl flex gap-1 mx-3 my-2 shrink-0"
        >
          <button
            id="tab-chats"
            type="button"
            onClick={() => setActiveTab('chats')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg text-xs transition-all ${
              activeTab === 'chats'
                ? 'bg-white/[0.08] text-white shadow-sm font-medium'
                : 'text-zinc-400 hover:text-white'
            }`}
            role="tab"
            aria-selected={activeTab === 'chats'}
            aria-controls="panel-chats"
          >
            <MessageSquare className="w-3.5 h-3.5" />
            <span>Cuộc trò chuyện</span>
          </button>
          <button
            id="tab-documents"
            type="button"
            onClick={() => setActiveTab('documents')}
            className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg text-xs transition-all ${
              activeTab === 'documents'
                ? 'bg-white/[0.08] text-white shadow-sm font-medium'
                : 'text-zinc-400 hover:text-white'
            }`}
            role="tab"
            aria-selected={activeTab === 'documents'}
            aria-controls="panel-documents"
          >
            <Files className="w-3.5 h-3.5" />
            <span>Tài liệu</span>
          </button>
        </div>

        {/* Error Alert Banner */}
        {currentError && (
          <div
            role="alert"
            className="mx-3 mb-2 p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-start justify-between gap-2 shadow-sm shrink-0"
          >
            <div className="flex items-start gap-2 min-w-0">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <span className="text-[11px] leading-tight break-words">{currentError}</span>
            </div>
            <button
              type="button"
              onClick={handleDismissError}
              aria-label="Dismiss sidebar error"
              className="text-rose-400 hover:text-rose-200 shrink-0 p-0.5 rounded transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Chats Tab Content */}
        <div
          id="panel-chats"
          role="tabpanel"
          aria-labelledby="tab-chats"
          className={activeTab === 'chats' ? 'flex flex-col flex-1 min-h-0' : 'hidden'}
        >
          {/* New Chat Button */}
          <div className="p-3 border-b border-white/[0.06] shrink-0">
            <button
              type="button"
              onClick={onNewChat}
              className="w-full bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 border border-sky-500/30 hover:border-sky-400/50 rounded-xl py-2 px-3 text-xs font-medium flex items-center justify-center gap-2 transition-all shadow-sm active:scale-[0.99]"
            >
              <Plus className="w-4 h-4" />
              <span>Cuộc trò chuyện mới</span>
            </button>
          </div>

          {/* Chat sessions header or selection toolbar */}
          {isSelectMode ? (
            <div className="px-3 pt-3 pb-2 flex items-center justify-between gap-1.5 border-b border-white/[0.06] bg-zinc-900/60 shrink-0">
              <div className="flex items-center gap-2 min-w-0">
                <label className="flex items-center gap-1.5 text-xs text-zinc-300 cursor-pointer">
                  <input
                    type="checkbox"
                    aria-label="Chọn tất cả"
                    checked={sessions.length > 0 && selectedSessionIds.size === sessions.length}
                    onChange={toggleSelectAll}
                    className="w-3.5 h-3.5 rounded bg-zinc-800 border-white/[0.2] text-sky-500 focus:ring-sky-400 focus:ring-offset-0 cursor-pointer accent-sky-500"
                  />
                  <span className="text-[11px] font-medium text-zinc-300 whitespace-nowrap">
                    Đã chọn {selectedSessionIds.size}
                  </span>
                </label>
              </div>

              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={handleDeleteSelected}
                  disabled={selectedSessionIds.size === 0}
                  aria-label={`Xóa đã chọn (${selectedSessionIds.size})`}
                  className={`text-[11px] px-2 py-0.5 rounded-lg font-medium transition-all flex items-center gap-1 ${
                    selectedSessionIds.size > 0
                      ? 'bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 border border-rose-500/30 shadow-sm cursor-pointer'
                      : 'bg-white/[0.04] text-zinc-500 border border-white/[0.06] cursor-not-allowed opacity-50'
                  }`}
                >
                  <Trash2 className="w-3 h-3" />
                  <span>Xóa đã chọn ({selectedSessionIds.size})</span>
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setIsSelectMode(false);
                    setSelectedSessionIds(new Set());
                  }}
                  aria-label="Hủy chọn"
                  className="text-[11px] px-2 py-0.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors"
                >
                  Hủy
                </button>
              </div>
            </div>
          ) : (
            <div className="px-3 pt-3 pb-2 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-zinc-300">
                <MessageSquare className="w-3.5 h-3.5 text-zinc-400" />
                <span>Cuộc trò chuyện gần đây</span>
              </div>
              <div className="flex items-center gap-1">
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-zinc-400 mr-0.5">
                  {sessions.length}
                </span>
                {sessions.length > 0 && (
                  <>
                    <button
                      type="button"
                      onClick={() => {
                        setIsSelectMode(true);
                        setSelectedSessionIds(new Set());
                      }}
                      aria-label="Chọn cuộc trò chuyện để xóa"
                      title="Chọn nhiều để xóa"
                      className="p-1 rounded-md text-zinc-400 hover:text-sky-300 hover:bg-white/[0.06] transition-colors"
                    >
                      <CheckSquare className="w-3.5 h-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={handleDeleteAllSessions}
                      aria-label="Xóa tất cả cuộc trò chuyện"
                      title="Xóa tất cả cuộc trò chuyện"
                      className="p-1 rounded-md text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </>
                )}
              </div>
            </div>
          )}

          {/* Sessions List */}
          <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-1.5 min-h-0">
            {sessions.length === 0 ? (
              <div className="text-center py-8 text-zinc-500">
                <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p className="text-xs">Chưa có cuộc trò chuyện nào</p>
                <p className="text-[10px] mt-1 text-zinc-600">
                  Bắt đầu một câu hỏi mới để lưu vào đây
                </p>
              </div>
            ) : (
              sessions.map((session) => {
                const isActive = activeSessionId === session.id;
                const isSelected = selectedSessionIds.has(session.id);
                return (
                  <div
                    key={session.id}
                    onClick={() => {
                      if (isSelectMode) {
                        toggleSelectSession(session.id);
                      } else {
                        onSelectSession?.(session.id);
                      }
                    }}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        if (isSelectMode) {
                          toggleSelectSession(session.id);
                        } else {
                          onSelectSession?.(session.id);
                        }
                      }
                    }}
                    className={`group flex items-center justify-between p-2.5 rounded-xl border text-xs cursor-pointer transition-all ${
                      isSelectMode && isSelected
                        ? 'bg-sky-500/10 border-sky-500/40 text-white shadow-sm'
                        : isActive && !isSelectMode
                        ? 'bg-white/[0.06] text-white border-l-2 border-sky-400 border-white/[0.08] shadow-sm font-medium'
                        : 'bg-zinc-900/30 hover:bg-white/[0.04] border-white/[0.04] hover:border-white/[0.08] text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0 pr-2">
                      {isSelectMode ? (
                        <input
                          type="checkbox"
                          aria-label={`Chọn ${session.title || 'Cuộc trò chuyện'}`}
                          checked={isSelected}
                          onClick={(e) => {
                            e.stopPropagation();
                          }}
                          onChange={() => {
                            toggleSelectSession(session.id);
                          }}
                          className="w-3.5 h-3.5 rounded bg-zinc-800 border-white/[0.2] text-sky-500 focus:ring-sky-400 cursor-pointer accent-sky-500 shrink-0"
                        />
                      ) : (
                        <MessageSquare
                          className={`w-3.5 h-3.5 shrink-0 ${
                            isActive ? 'text-sky-400' : 'text-zinc-500 group-hover:text-zinc-300'
                          }`}
                        />
                      )}
                      <div className="flex flex-col min-w-0">
                        <span className="truncate font-medium text-xs leading-tight" title={session.title}>
                          {session.title || 'Cuộc trò chuyện'}
                        </span>
                        {(session.updated_at || session.created_at) && (
                          <span className="text-[10px] text-zinc-500 mt-0.5">
                            {formatSessionDate(session.updated_at || session.created_at)}
                          </span>
                        )}
                      </div>
                    </div>

                    {!isSelectMode && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          const confirmed = window.confirm(
                            'Bạn có chắc chắn muốn xóa cuộc trò chuyện này không?'
                          );
                          if (confirmed) {
                            onDeleteSession?.(session.id);
                          }
                        }}
                        aria-label="Xóa cuộc trò chuyện"
                        title="Xóa cuộc trò chuyện"
                        className="p-1 rounded-lg text-zinc-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors shrink-0 opacity-80 md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Documents Tab Content */}
        <div
          id="panel-documents"
          role="tabpanel"
          aria-labelledby="tab-documents"
          className={activeTab === 'documents' ? 'flex flex-col flex-1 min-h-0' : 'hidden'}
        >
          {/* TopK slider section */}
          <div className="p-3 border-b border-white/[0.06] space-y-2 bg-zinc-900/40 shrink-0">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5 text-zinc-300 font-medium">
                <SlidersHorizontal className="w-3.5 h-3.5 text-sky-400" />
                <span>Độ sâu tìm kiếm</span>
              </div>
              <span className="font-mono text-[11px] px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400 border border-sky-500/20 font-medium">
                k = {topK}
              </span>
            </div>

            <input
              type="range"
              min="1"
              max="20"
              step="1"
              value={topK}
              onChange={(e) => onTopKChange(Number(e.target.value))}
              aria-label="Search depth topK"
              className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-sky-400 border border-white/[0.06] focus:outline-none"
            />

            <div className="flex justify-between text-[10px] text-zinc-500 font-mono">
              <span>1 đoạn</span>
              <span>20 đoạn</span>
            </div>
          </div>

          {/* File Dropzone */}
          <div className="p-3 border-b border-white/[0.06] shrink-0">
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt,.md,.png,.jpg,.jpeg"
              data-testid="file-upload-input"
              onChange={handleFileInputChange}
              className="hidden"
            />

            <div
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
              onClick={() => !isUploading && fileInputRef.current?.click()}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if ((e.key === 'Enter' || e.key === ' ') && !isUploading) {
                  fileInputRef.current?.click();
                }
              }}
              className={`border-dashed rounded-xl p-4 transition-all text-center cursor-pointer ${
                isDragging
                  ? 'border-sky-400 bg-sky-500/10 border-2'
                  : 'border border-white/[0.12] hover:border-sky-400/60 bg-white/[0.02] hover:bg-sky-500/[0.04]'
              }`}
            >
              {isUploading ? (
                <div className="flex flex-col items-center justify-center py-2 space-y-2">
                  <Loader2 className="w-6 h-6 text-sky-400 animate-spin" />
                  <span className="text-xs font-medium text-sky-300">
                    Đang tải lên và lập chỉ mục...
                  </span>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center space-y-2">
                  <div className="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 shadow-[0_0_12px_rgba(56,189,248,0.12)]">
                    <UploadCloud className="w-5 h-5" />
                  </div>
                  <div className="space-y-0.5">
                    <span className="text-xs font-medium text-white block">
                      Tải lên tài liệu
                    </span>
                    <span className="text-[11px] text-zinc-400 block">
                      Kéo thả hoặc nhấn để chọn tệp
                    </span>
                  </div>
                  <div className="flex items-center justify-center gap-1.5 pt-1 flex-wrap">
                    {['PDF', 'DOCX', 'TXT', 'Ảnh'].map((badge) => (
                      <span
                        key={badge}
                        className="text-[9px] font-mono px-1.5 py-0.5 rounded bg-white/[0.04] border border-white/[0.08] text-zinc-400"
                      >
                        {badge}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Indexed Documents List */}
          <div className="flex-1 flex flex-col min-h-0">
            <div className="p-3 pb-2 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-zinc-300">
                <Database className="w-3.5 h-3.5 text-zinc-400" />
                <span>Tài liệu đã lập chỉ mục</span>
              </div>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-zinc-400">
                {files.length}
              </span>
            </div>

            <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-1.5 min-h-0">
              {files.length === 0 ? (
                <div className="text-center py-8 text-zinc-500">
                  <FileText className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  <p className="text-xs">Chưa có tài liệu nào</p>
                  <p className="text-[10px] mt-1 text-zinc-600">
                    Tải tệp lên để bắt đầu phân tích
                  </p>
                </div>
              ) : (
                files.map((file) => (
                  <div
                    key={file.filename}
                    className="group flex items-center justify-between p-2.5 rounded-xl bg-zinc-900/40 hover:bg-white/[0.04] border border-white/[0.04] hover:border-white/[0.08] transition-colors"
                  >
                    <div className="flex items-center gap-2.5 min-w-0 pr-2">
                      <div className="w-7 h-7 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 shrink-0">
                        <FileText className="w-3.5 h-3.5" />
                      </div>
                      <div className="flex flex-col min-w-0">
                        <span
                          className="text-xs text-zinc-200 font-medium truncate"
                          title={file.filename}
                        >
                          {file.filename}
                        </span>
                        <span className="text-[10px] text-zinc-500 font-mono">
                          {formatFileSize(file.size)}
                        </span>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(file);
                      }}
                      aria-label={`Delete ${file.filename}`}
                      className="p-1 rounded-lg text-zinc-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors shrink-0"
                      title={`Xóa ${file.filename}`}
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
