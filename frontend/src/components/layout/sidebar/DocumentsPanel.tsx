import React, { useRef, useState } from 'react';
import { UploadCloud, FileText, Loader2, Database, SlidersHorizontal, Trash2 } from 'lucide-react';
import type { FileInfo } from '../../../types';
import { formatFileSize, isValidFileExtension } from './utils';

export interface DocumentsPanelProps {
  isActive: boolean;
  files: FileInfo[];
  topK: number;
  onTopKChange: (val: number) => void;
  onFileUpload: (file: File) => Promise<void>;
  onDeleteFile: (filename: string) => Promise<void>;
  isUploading?: boolean;
  onLocalError: (message: string | null) => void;
  onDismissError?: () => void;
}

const DocumentsPanel: React.FC<DocumentsPanelProps> = ({
  isActive,
  files,
  topK,
  onTopKChange,
  onFileUpload,
  onDeleteFile,
  isUploading = false,
  onLocalError,
  onDismissError,
}) => {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

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
        onLocalError(
          `Định dạng tệp "${droppedFile.name}" không được hỗ trợ. Vui lòng chọn .pdf, .docx, .txt hoặc .md`
        );
        return;
      }
      onLocalError(null);
      onDismissError?.();
      await onFileUpload(droppedFile);
    }
  };

  const handleFileInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (selectedFile) {
      if (!isValidFileExtension(selectedFile.name)) {
        onLocalError(
          `Định dạng tệp "${selectedFile.name}" không được hỗ trợ. Vui lòng chọn .pdf, .docx, .txt hoặc .md`
        );
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
        return;
      }
      onLocalError(null);
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
    <div
      id="panel-documents"
      role="tabpanel"
      aria-labelledby="tab-documents"
      className={isActive ? 'flex flex-col flex-1 min-h-0' : 'hidden'}
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
  );
};

export default DocumentsPanel;
