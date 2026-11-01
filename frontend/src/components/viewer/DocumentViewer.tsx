import React, { useState } from 'react';
import {
  FileText,
  FileQuestion,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Download,
  X,
  AlertCircle,
} from 'lucide-react';

export interface ActiveDocument {
  filename: string;
  page?: number;
}

export interface DocumentViewerProps {
  activeDocument: ActiveDocument | null;
  onClose: () => void;
  onPageChange?: (page: number) => void;
  className?: string;
}

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  activeDocument,
  onClose,
  onPageChange,
  className = '',
}) => {
  const currentPage = activeDocument?.page ?? 1;
  const [prevDocPage, setPrevDocPage] = useState<number | undefined>(activeDocument?.page);
  const [pageInput, setPageInput] = useState<string>(String(currentPage));

  if (activeDocument?.page !== prevDocPage) {
    setPrevDocPage(activeDocument?.page);
    setPageInput(String(activeDocument?.page ?? 1));
  }

  if (!activeDocument) {
    return (
      <div
        className={`h-full flex flex-col bg-obsidian-bg border-l border-obsidian-border ${className}`}
      >
        <div className="h-12 border-b border-obsidian-border bg-obsidian-surface px-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-obsidian-text-muted text-sm font-medium">
            <FileQuestion className="w-4 h-4 text-obsidian-accent-blue" />
            <span>Tài liệu</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close document viewer"
            className="p-1 rounded-md text-obsidian-text-muted hover:text-white hover:bg-obsidian-subtle transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center p-8 text-center">
          <div className="w-16 h-16 rounded-2xl bg-obsidian-subtle border border-obsidian-border/80 flex items-center justify-center mb-4 text-obsidian-text-muted">
            <FileQuestion className="w-8 h-8 opacity-70" />
          </div>
          <h3 className="text-sm font-medium text-obsidian-text mb-1">
            Chưa chọn tài liệu
          </h3>
          <p className="text-xs text-obsidian-text-muted max-w-xs leading-relaxed">
            Chọn hoặc bấm vào một trích dẫn tài liệu để xem nội dung
          </p>
        </div>
      </div>
    );
  }

  const { filename, page } = activeDocument;
  const isPdf = filename.toLowerCase().endsWith('.pdf');
  const encodedFilename = encodeURIComponent(filename);
  const fileUrl = `/api/v1/files/${encodedFilename}`;
  const pageAnchor = page ? `#page=${page}` : '';
  const viewerUrl = `${fileUrl}${pageAnchor}`;

  const handlePrevPage = () => {
    if (currentPage > 1) {
      onPageChange?.(currentPage - 1);
    }
  };

  const handleNextPage = () => {
    onPageChange?.(currentPage + 1);
  };

  const submitPageInput = () => {
    const val = parseInt(pageInput, 10);
    if (!isNaN(val) && val >= 1) {
      onPageChange?.(val);
    } else {
      setPageInput(String(currentPage));
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      submitPageInput();
    }
  };

  return (
    <div
      className={`h-full flex flex-col bg-obsidian-bg border-l border-obsidian-border ${className}`}
    >
      {/* Top Toolbar */}
      <div className="h-12 border-b border-obsidian-border bg-obsidian-surface px-3 sm:px-4 flex items-center justify-between gap-2 shrink-0">
        {/* Document Info & External Link */}
        <div className="flex items-center gap-2 min-w-0">
          <FileText className="w-4 h-4 text-obsidian-accent-blue shrink-0" />
          <span
            className="text-xs sm:text-sm font-medium font-mono text-obsidian-text truncate max-w-[140px] sm:max-w-[200px] lg:max-w-[260px]"
            title={filename}
          >
            {filename}
          </span>
          <a
            href={viewerUrl}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Open in new tab"
            title="Mở trong tab mới"
            className="p-1 rounded-md text-obsidian-text-muted hover:text-white hover:bg-obsidian-subtle transition-colors shrink-0"
          >
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>

        {/* Page Navigation Controls */}
        {isPdf && (
          <div className="flex items-center gap-1 bg-obsidian-subtle px-1.5 py-0.5 rounded-md border border-obsidian-border shrink-0">
            <button
              type="button"
              aria-label="Previous page"
              title="Trang trước"
              disabled={currentPage <= 1}
              onClick={handlePrevPage}
              className="p-1 rounded text-obsidian-text-muted hover:text-white disabled:opacity-30 disabled:hover:text-obsidian-text-muted disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <div className="flex items-center gap-1 text-[11px] text-obsidian-text-muted font-medium">
              <span>Trang</span>
              <input
                type="number"
                min={1}
                value={pageInput}
                onChange={(e) => setPageInput(e.target.value)}
                onBlur={submitPageInput}
                onKeyDown={handleKeyDown}
                aria-label="Page number"
                className="w-10 h-5 px-1 text-center text-xs bg-obsidian-surface border border-obsidian-border/80 rounded text-obsidian-text focus:outline-none focus:border-obsidian-accent-blue font-mono [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              />
            </div>
            <button
              type="button"
              aria-label="Next page"
              title="Trang sau"
              onClick={handleNextPage}
              className="p-1 rounded text-obsidian-text-muted hover:text-white transition-colors"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Action Controls */}
        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={onClose}
            aria-label="Close document viewer"
            title="Đóng xem tài liệu"
            className="p-1.5 rounded-md text-obsidian-text-muted hover:text-white hover:bg-obsidian-subtle transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Preview Area */}
      <div className="flex-1 min-h-0 flex flex-col relative bg-obsidian-bg">
        {isPdf ? (
          <div className="flex-1 flex flex-col h-full overflow-hidden">
            <iframe
              key={viewerUrl}
              src={viewerUrl}
              title="Document Preview"
              className="w-full flex-1 border-0 bg-obsidian-subtle"
            />
            {/* Fallback download bar */}
            <div className="h-9 px-4 border-t border-obsidian-border bg-obsidian-surface flex items-center justify-between text-xs text-obsidian-text-muted shrink-0">
              <span className="truncate">Gặp sự cố hiển thị tệp PDF?</span>
              <div className="flex items-center gap-3 shrink-0">
                <a
                  href={fileUrl}
                  download={filename}
                  aria-label="Download document"
                  title="Tải xuống tài liệu"
                  className="inline-flex items-center gap-1.5 text-obsidian-accent-blue hover:underline font-medium"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Tải xuống tài liệu</span>
                </a>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
            <div className="max-w-sm w-full bg-obsidian-surface border border-obsidian-border rounded-xl p-6 flex flex-col items-center shadow-lg">
              <div className="w-12 h-12 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mb-4">
                <AlertCircle className="w-6 h-6" />
              </div>
              <h4 className="text-sm font-medium text-obsidian-text mb-2">
                Không hỗ trợ xem trước trực tiếp
              </h4>
              <p className="text-xs text-obsidian-text-muted mb-5 leading-relaxed">
                Tệp <span className="font-mono text-obsidian-text font-semibold">{filename}</span> không phải định dạng PDF nên không thể hiển thị trực tiếp trong khung xem trước. Vui lòng tải về máy để xem nội dung đầy đủ.
              </p>
              <a
                href={fileUrl}
                download={filename}
                aria-label="Download document"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-obsidian-accent-blue/15 hover:bg-obsidian-accent-blue/25 text-obsidian-accent-blue border border-obsidian-accent-blue/30 font-medium text-xs transition-colors shadow-sm"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Tải xuống tài liệu</span>
              </a>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DocumentViewer;
