import React, { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Brain,
  CheckCircle2,
  Loader2,
  AlertCircle,
  Clock,
} from 'lucide-react';
import type { ReasoningStep } from '../../types';

export interface ReasoningStepsProps {
  steps?: ReasoningStep[];
  className?: string;
  defaultExpanded?: boolean;
}

const getNodeLabel = (nodeName: string): string => {
  const normalized = nodeName.toLowerCase().replace(/^\d+\.?\s*/, '').trim();
  switch (normalized) {
    case 'router':
      return 'Định tuyến câu hỏi (Router)';
    case 'expand_query':
      return 'Mở rộng truy vấn (Expand Query)';
    case 'hybrid_retrieve':
    case 'retrieve':
      return 'Truy xuất ngữ cảnh (Retrieve)';
    case 'rerank':
      return 'Tái xếp hạng liên quan (Rerank)';
    case 'grade_relevance':
    case 'grade':
      return 'Đánh giá độ phù hợp (Grade)';
    case 'rewrite_query':
    case 'rewrite':
      return 'Viết lại truy vấn (Rewrite)';
    case 'generate':
      return 'Tổng hợp câu trả lời (Generate)';
    case 'validate_citations':
      return 'Kiểm định trích dẫn (Validate Citations)';
    case 'abstain':
      return 'Từ chối trả lời (Abstain)';
    default:
      return nodeName;
  }
};

const getStatusIcon = (status?: string) => {
  switch (status) {
    case 'completed':
      return <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />;
    case 'in_progress':
      return <Loader2 className="w-3.5 h-3.5 text-obsidian-accent-blue animate-spin shrink-0" />;
    case 'failed':
      return <AlertCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />;
    default:
      return <Clock className="w-3.5 h-3.5 text-obsidian-text-muted shrink-0" />;
  }
};

export const ReasoningSteps: React.FC<ReasoningStepsProps> = ({
  steps,
  className = '',
  defaultExpanded = false,
}) => {
  const [isOpen, setIsOpen] = useState(defaultExpanded);

  if (!steps || steps.length === 0) {
    return null;
  }

  const completedCount = steps.filter((s) => s.status === 'completed').length;

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
          <Brain className="w-4 h-4 text-purple-400 shrink-0" />
          <span className="font-medium text-white">Quy trình suy luận</span>
          <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-purple-500/15 text-purple-300 border border-purple-500/30">
            {completedCount}/{steps.length} bước
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
        <div className="p-3 border-t border-obsidian-border/50 bg-obsidian-bg/40 space-y-2">
          {steps.map((step, idx) => (
            <div
              key={idx}
              className="flex items-start gap-2.5 p-2 rounded-md bg-obsidian-surface/70 border border-obsidian-border/40"
            >
              <div className="mt-0.5">{getStatusIcon(step.status)}</div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5 min-w-0 flex-wrap">
                    <span className="font-semibold text-white tracking-tight">
                      {getNodeLabel(step.node)}
                    </span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30">
                      {step.node.replace(/^\d+\.?\s*/, '').trim()}
                    </span>
                  </div>
                  {step.status && (
                    <span className="text-[10px] uppercase font-mono px-1 rounded bg-obsidian-subtle text-obsidian-text-muted border border-obsidian-border/60 shrink-0">
                      {step.status}
                    </span>
                  )}
                </div>
                {step.message && (
                  <p className="text-obsidian-text text-[11px] mt-0.5 leading-relaxed">
                    {step.message}
                  </p>
                )}
                {step.details && (
                  <p className="text-obsidian-text-muted text-[10.5px] mt-1 font-mono bg-obsidian-bg/70 p-1.5 rounded border border-obsidian-border/40 whitespace-pre-wrap break-all">
                    {step.details}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default ReasoningSteps;
