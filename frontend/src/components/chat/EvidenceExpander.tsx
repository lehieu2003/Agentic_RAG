import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Database,
  ExternalLink,
  FileText,
  Percent,
} from 'lucide-react';
import type { EvidenceChunk } from '../../types';

export interface EvidenceExpanderProps {
  evidence?: EvidenceChunk[];
  className?: string;
  defaultExpanded?: boolean;
  onCitationClick?: (filename: string, page?: number) => void;
}

export const EvidenceExpander: React.FC<EvidenceExpanderProps> = ({
  evidence,
  className = '',
  defaultExpanded = false,
  onCitationClick,
}) => {
  const [isOpen, setIsOpen] = useState(defaultExpanded);

  if (!evidence || evidence.length === 0) {
    return null;
  }

  return (
    <div className={`my-2.5 text-xs transition-all ${className}`}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full bg-zinc-900/60 hover:bg-zinc-900/90 border border-white/[0.08] hover:border-white/[0.12] rounded-xl px-3.5 py-2 flex items-center justify-between text-xs transition-all cursor-pointer select-none text-left group"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-2">
          <Database className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
          <span className="font-medium text-zinc-200">Dữ liệu trích dẫn</span>
          <span className="bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 px-2 py-0.5 rounded-full font-mono text-[10px]">
            {evidence.length} đoạn ngữ cảnh
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-zinc-400 group-hover:text-zinc-200 transition-colors">
          <span className="text-[11px] hidden sm:inline">
            {isOpen ? 'Thu gọn' : 'Chi tiết'}
          </span>
          {isOpen ? (
            <ChevronDown className="w-3.5 h-3.5" />
          ) : (
            <ChevronRight className="w-3.5 h-3.5" />
          )}
        </div>
      </button>

      {isOpen && (
        <div className="mt-2 space-y-2.5 max-h-[420px] overflow-y-auto p-3 bg-zinc-950/40 border border-white/[0.06] rounded-xl">
          {evidence.map((item, idx) => {
            const filename =
              item.filename ||
              item.doc_name ||
              item.chunk?.doc_name ||
              'Tài liệu trích dẫn';
            const page =
              item.page ?? item.page_number ?? item.chunk?.page_number;
            const text = item.text || item.content || item.chunk?.text || '';
            const score = item.score;

            return (
              <div
                key={item.id || idx}
                className="p-3 rounded-lg bg-zinc-900/60 border border-white/[0.08] hover:border-white/[0.14] transition-all space-y-2"
              >
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <FileText className="w-3.5 h-3.5 text-sky-400 shrink-0" />
                    {onCitationClick ? (
                      <button
                        type="button"
                        onClick={() => onCitationClick(filename, page)}
                        title={`Mở ${filename}${page !== undefined ? ` trang ${page}` : ''}`}
                        className="font-mono font-medium text-zinc-200 hover:text-sky-300 hover:underline text-[11.5px] truncate max-w-[200px] sm:max-w-[280px] text-left transition-colors"
                      >
                        {filename}
                      </button>
                    ) : (
                      <span className="font-mono font-medium text-zinc-200 text-[11.5px] truncate max-w-[200px] sm:max-w-[280px]">
                        {filename}
                      </span>
                    )}
                    {page !== undefined && (
                      <span className="bg-white/[0.04] border border-white/[0.08] text-sky-400 text-[10px] font-mono px-2 py-0.5 rounded">
                        Trang {page}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {score !== undefined && (
                      <span className="inline-flex items-center gap-0.5 text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded font-mono text-[10px]">
                        <Percent className="w-3 h-3" />
                        {(score > 1 ? score : score * 100).toFixed(1)}%
                      </span>
                    )}
                    {onCitationClick && (
                      <button
                        type="button"
                        onClick={() => onCitationClick(filename, page)}
                        aria-label="Mở PDF"
                        className="cursor-pointer text-sky-400 hover:text-sky-300 hover:underline inline-flex items-center gap-1 text-[11px] font-medium transition-colors"
                      >
                        <span>Mở PDF</span>
                        <ExternalLink className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>

                {text && (
                  <p className="text-zinc-400 text-xs leading-relaxed bg-zinc-950/40 p-2.5 rounded-lg border border-white/[0.04] font-sans whitespace-pre-wrap">
                    {text}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

export default EvidenceExpander;
