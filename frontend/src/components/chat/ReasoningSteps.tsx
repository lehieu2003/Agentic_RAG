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
      return <Loader2 className="w-3.5 h-3.5 text-sky-400 animate-spin shrink-0" />;
    case 'failed':
      return <AlertCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />;
    default:
      return <Clock className="w-3.5 h-3.5 text-zinc-500 shrink-0" />;
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
    <div className={`my-2.5 text-xs transition-all ${className}`}>
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full bg-zinc-900/60 hover:bg-zinc-900/90 border border-white/[0.08] hover:border-white/[0.12] rounded-xl px-3.5 py-2 flex items-center justify-between text-xs transition-all cursor-pointer select-none text-left group"
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-2">
          <Brain className="w-3.5 h-3.5 text-violet-400 shrink-0" />
          <span className="font-medium text-zinc-200">Quy trình suy luận</span>
          <span className="px-2 py-0.5 rounded-full font-mono text-[10px] bg-violet-500/10 text-violet-300 border border-violet-500/20">
            {completedCount}/{steps.length} bước
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
        <div className="mt-2 p-3 bg-zinc-950/40 border border-white/[0.06] rounded-xl space-y-3">
          <div className="border-l border-white/[0.08] ml-2 pl-3.5 space-y-3 py-1">
            {steps.map((step, idx) => (
              <div
                key={idx}
                className="relative flex items-start gap-2.5 p-2 rounded-lg bg-zinc-900/40 border border-white/[0.04] hover:border-white/[0.08] transition-colors"
              >
                <div className="mt-0.5">{getStatusIcon(step.status)}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2 flex-wrap">
                    <div className="flex items-center gap-1.5 min-w-0 flex-wrap">
                      <span className="font-semibold text-zinc-100 tracking-tight text-xs">
                        {getNodeLabel(step.node)}
                      </span>
                      <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-white/[0.04] text-zinc-300 border border-white/[0.08]">
                        {step.node.replace(/^\d+\.?\s*/, '').trim()}
                      </span>
                    </div>
                    {step.status && (
                      <span className="text-[10px] uppercase font-mono px-1.5 py-0.2 rounded bg-white/[0.04] text-zinc-400 border border-white/[0.06] shrink-0">
                        {step.status}
                      </span>
                    )}
                  </div>
                  {step.message && (
                    <p className="text-zinc-400 text-xs mt-1 leading-relaxed">
                      {step.message}
                    </p>
                  )}
                  {step.details && (
                    <p className="text-zinc-500 text-[10.5px] mt-1 font-mono bg-zinc-950/50 p-2 rounded-lg border border-white/[0.04] whitespace-pre-wrap break-all">
                      {step.details}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ReasoningSteps;
