import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import { Sparkles, User, FileText, RotateCcw } from 'lucide-react';
import type { ChatMessageData } from '../../types';
import CitationBadge from './CitationBadge';
import ReasoningSteps from './ReasoningSteps';
import EvidenceExpander from './EvidenceExpander';

export interface ChatMessageProps {
  message: ChatMessageData;
  onCitationClick: (filename: string, page?: number) => void;
  onRetry?: () => void;
  className?: string;
}

export const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  onCitationClick,
  onRetry,
  className = '',
}) => {
  const isUser = message.role === 'user';
  const hasCitations = message.citations && message.citations.length > 0;
  const hasReasoning = message.reasoning_steps && message.reasoning_steps.length > 0;
  const hasEvidence = message.evidence && message.evidence.length > 0;

  if (isUser) {
    return (
      <div className={`flex justify-end my-3 px-4 ${className}`}>
        <div className="flex items-start gap-2.5 max-w-[85%] sm:max-w-[75%] flex-row-reverse">
          <div className="w-8 h-8 rounded-full bg-obsidian-subtle border border-obsidian-border flex items-center justify-center text-obsidian-accent-blue shrink-0 mt-0.5">
            <User className="w-4 h-4" />
          </div>
          <div className="rounded-2xl rounded-tr-sm bg-obsidian-subtle border border-obsidian-border px-4 py-3 text-white text-sm shadow-md leading-relaxed whitespace-pre-wrap break-words select-text">
            {message.content}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex justify-start my-4 px-4 ${className}`}>
      <div className="flex items-start gap-3 max-w-full sm:max-w-4xl w-full">
        {/* Assistant Avatar */}
        <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0 mt-1 shadow-[0_0_12px_rgba(35,134,54,0.15)]">
          <Sparkles className="w-4 h-4" />
        </div>

        {/* Message Content Container */}
        <div className="flex-1 min-w-0">
          {/* Standalone Question Badge (if reformulated) */}
          {Boolean(message.standalone_question) && (
            <div className="mb-2.5 inline-flex items-center gap-1.5 rounded-full border border-obsidian-accent-blue/30 bg-obsidian-accent-blue/10 px-2.5 py-1 text-xs text-obsidian-accent-blue">
              <span>🔍 Đã hiểu ngữ cảnh: &quot;{message.standalone_question}&quot;</span>
            </div>
          )}

          {/* Reasoning Steps (if available) */}
          {hasReasoning && (
            <ReasoningSteps steps={message.reasoning_steps} />
          )}

          {/* Markdown Content with KaTeX & GFM */}
          <div className="prose-obsidian text-sm text-obsidian-text leading-relaxed break-words overflow-hidden select-text">
            <ReactMarkdown
              remarkPlugins={[remarkMath, remarkGfm]}
              rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
              components={{
                p: ({ children }) => <p className="mb-3 last:mb-0 leading-relaxed text-[13.5px]">{children}</p>,
                h1: ({ children }) => <h1 className="text-lg font-bold text-white mt-4 mb-2">{children}</h1>,
                h2: ({ children }) => <h2 className="text-base font-bold text-white mt-3 mb-2">{children}</h2>,
                h3: ({ children }) => <h3 className="text-sm font-semibold text-white mt-2.5 mb-1.5">{children}</h3>,
                ul: ({ children }) => <ul className="list-disc pl-5 mb-3 space-y-1 text-[13px]">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal pl-5 mb-3 space-y-1 text-[13px]">{children}</ol>,
                li: ({ children }) => <li className="leading-relaxed">{children}</li>,
                blockquote: ({ children }) => (
                  <blockquote className="border-l-2 border-emerald-500/50 pl-3 my-2 text-obsidian-text-muted italic bg-obsidian-subtle/30 py-1 rounded-r">
                    {children}
                  </blockquote>
                ),
                table: ({ children }) => (
                  <div className="my-3 overflow-x-auto rounded-lg border border-obsidian-border bg-obsidian-surface/60">
                    <table className="min-w-full divide-y divide-obsidian-border text-xs text-left">
                      {children}
                    </table>
                  </div>
                ),
                thead: ({ children }) => <thead className="bg-obsidian-subtle text-white font-semibold">{children}</thead>,
                th: ({ children }) => <th className="px-3 py-2 font-medium border-b border-obsidian-border">{children}</th>,
                td: ({ children }) => <td className="px-3 py-2 border-t border-obsidian-border/40 font-mono text-[11.5px]">{children}</td>,
                code: ({ children, className: codeClass }) => {
                  const isInline = !codeClass || !codeClass.includes('language-');
                  if (isInline) {
                    return (
                      <code className="px-1.5 py-0.5 rounded bg-obsidian-subtle border border-obsidian-border text-emerald-300 font-mono text-[12px]">
                        {children}
                      </code>
                    );
                  }
                  return (
                    <code className="block p-3 rounded-lg bg-obsidian-bg border border-obsidian-border text-emerald-300 font-mono text-xs overflow-x-auto my-2.5">
                      {children}
                    </code>
                  );
                },
                a: ({ href, children }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-obsidian-accent-blue hover:underline font-medium"
                  >
                    {children}
                  </a>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>

          {/* Citations section */}
          {hasCitations && (
            <div className="mt-3.5 pt-3 border-t border-obsidian-border/50">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-white mb-2">
                <FileText className="w-3.5 h-3.5 text-obsidian-accent-blue" />
                <span>Nguồn trích dẫn:</span>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                {message.citations!.map((cit, idx) => (
                  <CitationBadge
                    key={idx}
                    citation={cit}
                    onClick={onCitationClick}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Evidence Expander section */}
          {hasEvidence && (
            <EvidenceExpander
              evidence={message.evidence}
              onCitationClick={onCitationClick}
            />
          )}

          {/* Retry Button on Error */}
          {message.isError && onRetry && (
            <div className="mt-3">
              <button
                type="button"
                onClick={onRetry}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-medium transition-colors cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Thử lại</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ChatMessage;
