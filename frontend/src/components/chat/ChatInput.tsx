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
      <div className="relative rounded-2xl bg-obsidian-surface border border-obsidian-border focus-within:border-obsidian-accent-blue/60 shadow-lg transition-all duration-200">
        <textarea
          ref={textareaRef}
          rows={1}
          value={content}
          disabled={isQuerying}
          onChange={(e) => setContent(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={effectivePlaceholder}
          className="w-full bg-transparent text-white placeholder-obsidian-text-muted text-sm px-4 pt-3.5 pb-10 resize-none outline-none disabled:opacity-50 disabled:cursor-not-allowed max-h-40 min-h-[48px] font-sans"
        />

        {/* Action bar inside textarea */}
        <div className="absolute left-3 right-3 bottom-2.5 flex items-center justify-between pointer-events-none">
          <div className="flex items-center gap-2 text-[11px] text-obsidian-text-muted font-mono pointer-events-auto">
            <span className="hidden sm:inline-flex items-center gap-1">
              <Sparkles className="w-3 h-3 text-obsidian-accent-blue" />
              <span>Hỗ trợ KaTeX &amp; TCVN</span>
            </span>
          </div>

          <button
            type="button"
            onClick={handleSend}
            disabled={isQuerying || content.trim().length === 0}
            aria-label="Gửi tin nhắn"
            className="pointer-events-auto p-2 rounded-xl bg-obsidian-accent hover:bg-emerald-600 disabled:bg-obsidian-subtle text-white disabled:text-obsidian-text-muted disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-150 flex items-center justify-center cursor-pointer shadow-sm hover:shadow-[0_0_12px_rgba(35,134,54,0.3)]"
          >
            {isQuerying ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </div>
      </div>
      <div className="mt-2 text-center text-[11px] text-obsidian-text-muted">
        Nhấn <kbd className="px-1 py-0.5 rounded bg-obsidian-subtle border border-obsidian-border text-[10px] font-mono">Enter</kbd> để gửi, <kbd className="px-1 py-0.5 rounded bg-obsidian-subtle border border-obsidian-border text-[10px] font-mono">Shift + Enter</kbd> để xuống dòng
      </div>
    </div>
  );
};

export default ChatInput;
