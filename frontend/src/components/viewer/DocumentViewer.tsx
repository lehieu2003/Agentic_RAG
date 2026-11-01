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
  const docKey = activeDocument ? `${activeDocument.filename}:${activeDocument.page ?? 1}` : '';
  const [prevDocKey, setPrevDocKey] = useState<string>(docKey);
  const [pageInput, setPageInput] = useState<string>(String(currentPage));

  if (docKey !== prevDocKey) {
    setPrevDocKey(docKey);
    setPageInput(String(activeDocument?.page ?? 1));
  }

  if (!activeDocument) {
    return (
      <div
        className={`h-full flex flex-col bg-zinc-950 ${className}`}
      >
        <div className="h-[52px] bg-zinc-950/80 backdrop-blur-md border-b border-white/[0.06] px-4 flex items-center justify-between gap-3 shrink-0">
          <div className="flex items-center gap-2 text-zinc-400 text-sm font-medium">
            <div className="w-7 h-7 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center shrink-0">
              <FileQuestion className="w-3.5 h-3.5 text-sky-400" />
            </div>
            <span>Tài liệu</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close document viewer"
            title="Đóng xem tài liệu"
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="flex-1 flex flex-col items-center justify-center h-full p-8 text-center bg-zinc-950/50">
          <div className="relative mb-4">
            <div className="absolute -inset-2 bg-sky-500/10 rounded-2xl blur-lg pointer-events-none" />
            <div className="relative w-14 h-14 rounded-2xl bg-zinc-900 border border-white/[0.08] flex items-center justify-center text-zinc-400">
              <FileQuestion className="w-7 h-7 text-zinc-500" />
            </div>
          </div>
          <h3 className="text-sm font-medium text-zinc-200 mb-1.5">
            Chưa chọn tài liệu
          </h3>
          <p className="text-xs text-zinc-400 max-w-xs leading-relaxed mb-3">
            Chọn hoặc bấm vào một trích dẫn để xem tài liệu nguồn
          </p>
          <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-white/[0.03] border border-white/[0.06] text-[11px] text-zinc-500 font-mono">
            <span>Hỗ trợ PDF, DOCX, TXT, MD</span>
          </div>
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
      className={`h-full flex flex-col bg-zinc-950 ${className}`}
    >
      {/* Top Toolbar */}
      <div className="h-[52px] bg-zinc-950/80 backdrop-blur-md border-b border-white/[0.06] px-4 flex items-center justify-between gap-3 shrink-0">
        {/* Document Title */}
        <div className="flex items-center gap-2.5 min-w-0">
          <div className="w-7 h-7 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center shrink-0">
            <FileText className="w-3.5 h-3.5 text-sky-400" />
          </div>
          <span
            className="text-sm font-medium text-zinc-100 font-mono truncate max-w-[140px] sm:max-w-[200px] lg:max-w-[260px]"
            title={filename}
          >
            {filename}
          </span>
        </div>

        {/* Page Navigation Controls */}
        {isPdf && (
          <div className="flex items-center gap-1 bg-white/[0.04] border border-white/[0.08] rounded-lg px-2 py-1 text-xs shrink-0">
            <button
              type="button"
              aria-label="Previous page"
              title="Trang trước"
              disabled={currentPage <= 1}
              onClick={handlePrevPage}
              className="p-1 hover:bg-white/[0.06] rounded text-zinc-400 hover:text-white disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-3.5 h-3.5" />
            </button>
            <div className="flex items-center gap-1 text-[11px] text-zinc-400 font-medium px-1">
              <span>Trang</span>
              <input
                type="number"
                min={1}
                value={pageInput}
                onChange={(e) => setPageInput(e.target.value)}
                onBlur={submitPageInput}
                onKeyDown={handleKeyDown}
                aria-label="Page number"
                className="w-10 text-center font-mono bg-zinc-900 border border-white/[0.1] rounded text-xs py-0.5 text-white focus:outline-none focus:border-sky-500/50 [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none"
              />
            </div>
            <button
              type="button"
              aria-label="Next page"
              title="Trang sau"
              onClick={handleNextPage}
              className="p-1 hover:bg-white/[0.06] rounded text-zinc-400 hover:text-white transition-colors"
            >
              <ChevronRight className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Action Controls */}
        <div className="flex items-center gap-1 shrink-0">
          <a
            href={viewerUrl}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="Open in new tab"
            title="Mở trong tab mới"
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors"
          >
            <ExternalLink className="w-4 h-4" />
          </a>
          {isPdf && (
            <a
              href={fileUrl}
              download={filename}
              aria-label="Download document"
              title="Tải xuống tài liệu"
              className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors"
            >
              <Download className="w-4 h-4" />
            </a>
          )}
          <button
            type="button"
            onClick={onClose}
            aria-label="Close document viewer"
            title="Đóng xem tài liệu"
            className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Preview Area */}
      <div className="flex-1 min-h-0 flex flex-col relative bg-zinc-950">
        {isPdf ? (
          <div className="flex-1 flex flex-col h-full overflow-hidden">
            <iframe
              key={viewerUrl}
              src={viewerUrl}
              title="Document Preview"
              className="w-full flex-1 border-0 bg-zinc-950"
            />
          </div>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center p-6 text-center">
            <div className="max-w-sm w-full bg-amber-500/10 border border-amber-500/20 text-amber-200 text-xs p-5 rounded-xl flex flex-col items-center text-center gap-3 shadow-lg">
              <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex items-center justify-center text-amber-400 shrink-0">
                <AlertCircle className="w-5 h-5" />
              </div>
              <div className="space-y-1.5">
                <h4 className="text-sm font-medium text-amber-100">
                  Không hỗ trợ xem trước trực tiếp
                </h4>
                <p className="text-amber-200/80 leading-relaxed">
                  Tệp <span className="font-mono text-white font-semibold">{filename}</span> không phải định dạng PDF nên không thể hiển thị trực tiếp trong khung xem trước. Vui lòng tải về máy để xem nội dung đầy đủ.
                </p>
              </div>
              <a
                href={fileUrl}
                download={filename}
                aria-label="Download document"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500/20 hover:bg-amber-500/30 text-amber-100 border border-amber-500/30 font-medium text-xs transition-colors shadow-sm"
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
