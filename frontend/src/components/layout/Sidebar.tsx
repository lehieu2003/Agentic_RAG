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
} from 'lucide-react';
import type { FileInfo } from '../../types';

export interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
  files: FileInfo[];
  topK: number;
  onTopKChange: (val: number) => void;
  onNewChat: () => void;
  onFileUpload: (file: File) => Promise<void>;
  onDeleteFile: (filename: string) => Promise<void>;
  isUploading?: boolean;
}

function formatFileSize(bytes: number): string {
  if (!bytes || bytes <= 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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
  isUploading = false,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) {
    return null;
  }

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
      await onFileUpload(droppedFile);
    }
  };

  const handleFileInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      await onFileUpload(selectedFile);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
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

      <aside className="fixed inset-y-0 left-0 z-40 md:relative md:z-0 flex flex-col w-72 sm:w-80 h-full bg-obsidian-surface border-r border-obsidian-border text-obsidian-text select-none shrink-0">
        {/* Header / New Chat action */}
        <div className="p-3 border-b border-obsidian-border space-y-2">
          <div className="flex items-center justify-between md:hidden">
            <span className="text-xs font-semibold text-white tracking-wide uppercase">
              Bảng điều khiển
            </span>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close sidebar"
              className="p-1 rounded-md text-obsidian-text-muted hover:text-white hover:bg-obsidian-subtle transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>

          <button
            type="button"
            onClick={onNewChat}
            className="flex items-center justify-center gap-2 w-full py-2 px-3 rounded-lg bg-obsidian-subtle hover:bg-[#282e37] border border-obsidian-border text-white text-xs font-semibold tracking-wide transition-all shadow-sm active:scale-[0.99]"
          >
            <Plus className="w-4 h-4 text-emerald-400" />
            <span>Cuộc trò chuyện mới</span>
          </button>
        </div>

        {/* TopK slider section */}
        <div className="p-3 border-b border-obsidian-border space-y-2 bg-obsidian-bg/40">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-1.5 text-obsidian-text font-medium">
              <SlidersHorizontal className="w-3.5 h-3.5 text-obsidian-accent-blue" />
              <span>Độ sâu tìm kiếm</span>
            </div>
            <span className="font-mono text-[11px] px-1.5 py-0.5 rounded bg-obsidian-bg text-obsidian-accent-blue border border-obsidian-border">
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
            className="w-full h-1.5 bg-obsidian-bg rounded-lg appearance-none cursor-pointer accent-emerald-500 border border-obsidian-border focus:outline-none"
          />

          <div className="flex justify-between text-[10px] text-obsidian-text-muted">
            <span>1 đoạn</span>
            <span>20 đoạn</span>
          </div>
        </div>

        {/* File Dropzone */}
        <div className="p-3 border-b border-obsidian-border">
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx,.txt,.md"
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
            className={`border border-dashed rounded-lg p-3 text-center transition-all cursor-pointer ${
              isDragging
                ? 'border-emerald-500 bg-emerald-500/10'
                : 'border-obsidian-border hover:border-obsidian-text-muted/60 bg-obsidian-bg/40 hover:bg-obsidian-subtle/50'
            }`}
          >
            {isUploading ? (
              <div className="flex flex-col items-center justify-center py-2 space-y-2">
                <Loader2 className="w-6 h-6 text-emerald-400 animate-spin" />
                <span className="text-xs font-medium text-emerald-300">
                  Đang tải lên và lập chỉ mục...
                </span>
              </div>
            ) : (
              <div className="flex flex-col items-center justify-center py-1 space-y-1">
                <UploadCloud className="w-5 h-5 text-obsidian-accent-blue" />
                <span className="text-xs font-medium text-white">
                  Tải lên tài liệu
                </span>
                <span className="text-[10px] text-obsidian-text-muted">
                  Kéo thả hoặc nhấn để chọn (.pdf, .docx, .txt, .md)
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Indexed Documents List */}
        <div className="flex-1 flex flex-col min-h-0">
          <div className="p-3 pb-2 flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-obsidian-text">
              <Database className="w-3.5 h-3.5 text-obsidian-text-muted" />
              <span>Tài liệu đã lập chỉ mục</span>
            </div>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-obsidian-subtle border border-obsidian-border text-obsidian-text-muted">
              {files.length}
            </span>
          </div>

          <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-1.5">
            {files.length === 0 ? (
              <div className="text-center py-8 text-obsidian-text-muted">
                <FileText className="w-8 h-8 mx-auto mb-2 opacity-30" />
                <p className="text-xs">Chưa có tài liệu nào</p>
                <p className="text-[10px] mt-1 text-obsidian-text-muted/70">
                  Tải tệp lên để bắt đầu phân tích
                </p>
              </div>
            ) : (
              files.map((file) => (
                <div
                  key={file.filename}
                  className="flex items-center justify-between p-2 rounded-lg bg-obsidian-bg/50 hover:bg-obsidian-subtle border border-obsidian-border/50 transition-colors group"
                >
                  <div className="flex items-center gap-2 min-w-0 pr-2">
                    <FileText className="w-4 h-4 text-emerald-400 shrink-0" />
                    <div className="flex flex-col min-w-0">
                      <span
                        className="text-xs text-obsidian-text font-medium truncate"
                        title={file.filename}
                      >
                        {file.filename}
                      </span>
                      <span className="text-[10px] text-obsidian-text-muted">
                        {formatFileSize(file.size)}
                      </span>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      onDeleteFile(file.filename);
                    }}
                    aria-label={`Delete ${file.filename}`}
                    className="p-1 rounded text-obsidian-text-muted hover:text-rose-400 hover:bg-rose-950/40 transition-colors shrink-0"
                    title={`Xóa ${file.filename}`}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
