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
      className={`group inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium 
        bg-obsidian-subtle/80 hover:bg-obsidian-subtle text-obsidian-text hover:text-white 
        border border-obsidian-border hover:border-obsidian-accent-blue/60 transition-all 
        shadow-sm hover:shadow-[0_0_12px_rgba(88,166,255,0.15)] cursor-pointer text-left ${className}`}
    >
      <FileText className="w-3.5 h-3.5 text-obsidian-accent-blue shrink-0 group-hover:scale-110 transition-transform" />
      <span className="truncate max-w-[180px] sm:max-w-[240px] font-mono text-[11.5px]">
        {filename}
      </span>
      {page !== undefined && (
        <span className="inline-flex items-center px-1.5 py-0.2 rounded text-[10.5px] font-semibold bg-obsidian-surface text-obsidian-accent-blue border border-obsidian-border/70 shrink-0">
          Trang {page}
        </span>
      )}
    </button>
  );
};

export default CitationBadge;
