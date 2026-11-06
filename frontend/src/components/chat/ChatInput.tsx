import React, { useState, useRef, useEffect } from 'react';
import { Send, Loader2, Sparkles } from 'lucide-react';

export interface ChatInputProps {
  onSendMessage: (msg: string) => void;
  isQuerying: boolean;
  className?: string;
  placeholder?: string;
}

export const ChatInput: React.FC<ChatInputProps> = ({
  onSendMessage,
  isQuerying,
  className = '',
  placeholder,
}) => {
  const [content, setContent] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea based on content
  const adjustHeight = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = 'auto';
      el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
    }
  };

  useEffect(() => {
    adjustHeight();
  }, [content]);

  const handleSend = () => {
    if (isQuerying) return;
    const trimmed = content.trim();
    if (!trimmed) return;
    onSendMessage(trimmed);
    setContent('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.nativeEvent.isComposing) return;
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const effectivePlaceholder = isQuerying
    ? 'Hệ thống đang xử lý câu trả lời...'
    : placeholder || 'Nhập câu hỏi kỹ thuật... (Shift+Enter để xuống dòng)';

  return (
    <div className={`w-full max-w-4xl mx-auto px-4 ${className}`}>
      <div className="relative rounded-2xl bg-zinc-900/85 backdrop-blur-xl border border-white/[0.1] focus-within:border-sky-500/60 shadow-[0_8px_32px_rgb(0_0_0/var(--shadow-alpha))] transition-all duration-200">
        <textarea
          ref={textareaRef}
          rows={1}
          value={content}
          disabled={isQuerying}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          aria-label="Nhập câu hỏi kỹ thuật"
          placeholder={effectivePlaceholder}
          className="w-full bg-transparent text-white placeholder-zinc-500 text-sm px-4 pt-3.5 pb-10 resize-none outline-none disabled:opacity-50 disabled:cursor-not-allowed max-h-40 min-h-[48px] font-sans"
        />

        {/* Action bar inside textarea */}
        <div className="absolute left-3 right-3 bottom-2.5 flex items-center justify-between pointer-events-none">
          <div className="flex items-center gap-2 text-[11px] font-mono text-zinc-500 pointer-events-auto">
            <span className="hidden sm:inline-flex items-center gap-1.5">
              <Sparkles className="w-3.5 h-3.5 text-sky-400" />
              <span>Hỗ trợ KaTeX &amp; TCVN</span>
            </span>
          </div>

          <button
            type="button"
            onClick={handleSend}
            disabled={isQuerying || content.trim().length === 0}
            aria-label="Gửi tin nhắn"
            className="pointer-events-auto p-2 rounded-xl bg-sky-500 hover:bg-sky-400 disabled:bg-zinc-800 text-zinc-950 disabled:text-zinc-500 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-150 flex items-center justify-center cursor-pointer shadow-sm hover:shadow-[0_0_16px_rgba(56,189,248,0.4)]"
          >
            {isQuerying ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>
      <div className="mt-2 text-center text-[11px] text-zinc-500">
        Nhấn <kbd className="px-1.5 py-0.5 rounded bg-zinc-800/80 border border-white/[0.08] text-[10px] font-mono text-zinc-400">Enter</kbd> để gửi, <kbd className="px-1.5 py-0.5 rounded bg-zinc-800/80 border border-white/[0.08] text-[10px] font-mono text-zinc-400">Shift + Enter</kbd> để xuống dòng
      </div>
    </div>
  );
};

export default ChatInput;
