import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Database,
  ExternalLink,
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
    <div
      className={`rounded-lg border border-obsidian-border bg-obsidian-surface/60 overflow-hidden text-xs my-2.5 transition-all ${className}`}
    >
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-3.5 py-2.5 flex items-center justify-between bg-obsidian-surface/80 hover:bg-obsidian-subtle text-obsidian-text hover:text-white transition-colors cursor-pointer select-none text-left"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-2">
          <Database className="w-4 h-4 text-emerald-400 shrink-0" />
          <span className="font-medium text-white">Dữ liệu trích dẫn</span>
          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
            {evidence.length} đoạn ngữ cảnh
          </span>
        </div>
        <div className="flex items-center gap-1.5 text-obsidian-text-muted">
          <span className="text-[11px] hidden sm:inline">
            {isOpen ? 'Thu gọn' : 'Chi tiết'}
          </span>
          {isOpen ? (
            <ChevronDown className="w-4 h-4" />
          ) : (
            <ChevronRight className="w-4 h-4" />
          )}
        </div>
      </button>

      {isOpen && (
        <div className="p-3 border-t border-obsidian-border/50 bg-obsidian-bg/40 space-y-2.5 max-h-[380px] overflow-y-auto">
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
                className="p-2.5 rounded-md bg-obsidian-surface/80 border border-obsidian-border/60 hover:border-obsidian-border transition-colors space-y-1.5"
              >
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span className="font-semibold text-white font-mono text-[11px] truncate max-w-[200px] sm:max-w-[280px]">
                      {filename}
                    </span>
                    {page !== undefined && (
                      <span className="px-1.5 py-0.2 rounded text-[10.5px] font-mono bg-obsidian-subtle text-obsidian-accent-blue border border-obsidian-border/80">
                        Trang {page}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {score !== undefined && (
                      <span className="inline-flex items-center gap-0.5 text-[10.5px] font-mono text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">
                        <Percent className="w-3 h-3" />
                        {(score > 1 ? score : score * 100).toFixed(1)}%
                      </span>
                    )}
                    {onCitationClick && (
                      <button
                        type="button"
                        onClick={() => onCitationClick(filename, page)}
                        className="inline-flex items-center gap-1 text-[10.5px] text-obsidian-accent-blue hover:underline cursor-pointer"
                      >
                        <span>Mở PDF</span>
                        <ExternalLink className="w-3 h-3" />
                      </button>
                    )}
                  </div>
                </div>

                {text && (
                  <p className="text-obsidian-text text-[11.5px] leading-relaxed bg-obsidian-bg/60 p-2 rounded border border-obsidian-border/40 whitespace-pre-wrap font-sans">
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
