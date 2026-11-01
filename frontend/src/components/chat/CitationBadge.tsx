import React from 'react';
import { FileText } from 'lucide-react';
import type { Citation } from '../../types';

export interface CitationBadgeProps {
  citation: Citation;
  onClick: (filename: string, page?: number) => void;
  className?: string;
}

export const CitationBadge: React.FC<CitationBadgeProps> = ({
  citation,
  onClick,
  className = '',
}) => {
  const filename = citation.filename || citation.doc_name || 'Tài liệu';
  const page = citation.page ?? citation.page_number;

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.preventDefault();
    onClick(filename, page);
  };

  return (
    <button
      type="button"
      onClick={handleClick}
      title={`${filename}${page !== undefined ? ` (Trang ${page})` : ''} - Bấm để mở tài liệu`}
      className={`group inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg 
        bg-sky-500/10 hover:bg-sky-500/20 border border-sky-500/25 hover:border-sky-400/50 
        text-sky-400 text-xs font-mono transition-all duration-150 cursor-pointer 
        shadow-sm hover:shadow-[0_0_12px_rgba(56,189,248,0.2)] text-left ${className}`}
    >
      <FileText className="w-3.5 h-3.5 text-sky-400 shrink-0 group-hover:scale-110 transition-transform" />
      <span className="truncate max-w-[180px] sm:max-w-[240px] font-mono text-[11.5px] text-zinc-200 group-hover:text-white transition-colors">
        {filename}
      </span>
      {page !== undefined && (
        <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-sky-500/15 text-sky-300 border border-sky-500/30 shrink-0">
          Trang {page}
        </span>
      )}
    </button>
  );
};

export default CitationBadge;
