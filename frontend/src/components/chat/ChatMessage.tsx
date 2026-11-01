import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import {
  Sparkles,
  User,
  FileText,
  RotateCcw,
  Copy,
  Check,
} from 'lucide-react';
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

interface CodeBlockProps {
  className?: string;
  children: React.ReactNode;
}

const CodeBlock: React.FC<CodeBlockProps> = ({ className, children }) => {
  const [copied, setCopied] = useState(false);
  const isInline = !className || !className.includes('language-');
  const language = className ? className.replace('language-', '') : '';

  if (isInline) {
    return (
      <code className="px-1.5 py-0.5 rounded bg-white/[0.06] border border-white/[0.08] text-emerald-300 font-mono text-[12px]">
        {children}
      </code>
    );
  }

  const handleCopy = async () => {
    try {
      const textToCopy = String(children).replace(/\n$/, '');
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(textToCopy);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    } catch {
      // Ignore clipboard write failures in restricted environments
    }
  };

  return (
    <div className="rounded-xl bg-zinc-950/80 border border-white/[0.08] overflow-hidden my-3 shadow-sm">
      <div className="flex items-center justify-between px-3.5 py-1.5 bg-white/[0.03] border-b border-white/[0.06] text-xs font-mono text-zinc-400">
        <span className="text-[11px] font-medium text-zinc-300">{language || 'code'}</span>
        <button
          type="button"
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-[11px] text-zinc-400 hover:text-zinc-200 transition-colors cursor-pointer py-0.5 px-1 rounded hover:bg-white/[0.04]"
          title="Sao chép mã"
          aria-label="Sao chép mã"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400 font-sans">Đã sao chép!</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5" />
              <span className="font-sans">Sao chép</span>
            </>
          )}
        </button>
      </div>
      <pre className="p-3.5 overflow-x-auto text-xs font-mono text-emerald-300 leading-relaxed">
        <code>{children}</code>
      </pre>
    </div>
  );
};

export const ChatMessage: React.FC<ChatMessageProps> = ({
  message,
  onCitationClick,
  onRetry,
  className = '',
}) => {
  const isUser = message.role === 'user';
  const hasCitations = message.citations && message.citations.length > 0;
  const hasReasoning =
    message.reasoning_steps && message.reasoning_steps.length > 0;
  const hasEvidence = message.evidence && message.evidence.length > 0;

  if (isUser) {
    return (
      <div className={`flex justify-end my-3 px-4 ${className}`}>
        <div className="flex items-start gap-2.5 max-w-[85%] sm:max-w-[75%] flex-row-reverse">
          <div className="w-8 h-8 rounded-full bg-white/[0.06] border border-white/[0.08] flex items-center justify-center text-sky-400 shrink-0 mt-0.5">
            <User className="w-4 h-4" />
          </div>
          <div className="rounded-2xl rounded-tr-sm bg-zinc-800/90 border border-white/[0.08] px-4 py-3 text-zinc-100 text-sm shadow-md leading-relaxed whitespace-pre-wrap break-words select-text">
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
        <div className="w-7 h-7 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 shrink-0 mt-1 shadow-[0_0_12px_rgba(56,189,248,0.15)]">
          <Sparkles className="w-3.5 h-3.5" />
        </div>

        {/* Message Content Container */}
        <div className="flex-1 min-w-0">
          {/* Standalone Question Badge (if reformulated) */}
          {Boolean(message.standalone_question) && (
            <div className="mb-2.5 inline-flex items-center gap-1.5 rounded-full border border-sky-500/30 bg-sky-500/10 px-3 py-1 text-xs text-sky-400 font-medium">
              <span>
                🔍 Đã hiểu ngữ cảnh: &quot;{message.standalone_question}&quot;
              </span>
            </div>
          )}

          {/* Reasoning Steps (if available) */}
          {hasReasoning && (
            <ReasoningSteps steps={message.reasoning_steps} />
          )}

          {/* Markdown Content with KaTeX & GFM */}
          <div className="text-sm text-zinc-300 leading-relaxed break-words overflow-hidden select-text">
            <ReactMarkdown
              remarkPlugins={[remarkMath, remarkGfm]}
              rehypePlugins={[[rehypeKatex, { throwOnError: false, strict: false }]]}
              components={{
                p: ({ children }) => (
                  <p className="mb-3 last:mb-0 leading-relaxed text-[13.5px] text-zinc-300">
                    {children}
                  </p>
                ),
                h1: ({ children }) => (
                  <h1 className="text-lg font-bold text-white mt-4 mb-2 tracking-tight">
                    {children}
                  </h1>
                ),
                h2: ({ children }) => (
                  <h2 className="text-base font-bold text-white mt-3.5 mb-2 tracking-tight">
                    {children}
                  </h2>
                ),
                h3: ({ children }) => (
                  <h3 className="text-sm font-semibold text-zinc-100 mt-2.5 mb-1.5">
                    {children}
                  </h3>
                ),
                ul: ({ children }) => (
                  <ul className="list-disc pl-5 mb-3 space-y-1 text-[13px] text-zinc-300">
                    {children}
                  </ul>
                ),
                ol: ({ children }) => (
                  <ol className="list-decimal pl-5 mb-3 space-y-1 text-[13px] text-zinc-300">
                    {children}
                  </ol>
                ),
                li: ({ children }) => (
                  <li className="leading-relaxed">{children}</li>
                ),
                blockquote: ({ children }) => (
                  <blockquote className="border-l-2 border-emerald-500 pl-3.5 my-2.5 text-zinc-400 italic bg-emerald-500/5 py-1.5 rounded-r-lg">
                    {children}
                  </blockquote>
                ),
                table: ({ children }) => (
                  <div className="my-3 overflow-x-auto rounded-xl border border-white/[0.08] bg-zinc-900/60 shadow-sm">
                    <table className="min-w-full divide-y divide-white/[0.06] text-xs text-left">
                      {children}
                    </table>
                  </div>
                ),
                thead: ({ children }) => (
                  <thead className="bg-zinc-800/60 text-zinc-200 font-semibold">
                    {children}
                  </thead>
                ),
                th: ({ children }) => (
                  <th className="px-3.5 py-2.5 font-medium border-b border-white/[0.08]">
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td className="px-3.5 py-2 border-t border-white/[0.04] font-mono text-[11.5px] text-zinc-300">
                    {children}
                  </td>
                ),
                code: ({ children, className: codeClass }) => (
                  <CodeBlock className={codeClass}>{children}</CodeBlock>
                ),
                a: ({ href, children }) => (
                  <a
                    href={href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sky-400 hover:text-sky-300 hover:underline font-medium transition-colors"
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
            <div className="mt-3.5 pt-3 border-t border-white/[0.08]">
              <div className="flex items-center gap-1.5 text-xs font-semibold text-zinc-200 mb-2">
                <FileText className="w-3.5 h-3.5 text-sky-400" />
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
