import React, { useRef, useEffect } from 'react';
import { Loader2, Sparkles } from 'lucide-react';
import type { ChatMessageData } from '../../types';
import ChatMessage from './ChatMessage';
import EmptyHero from './EmptyHero';
import ChatInput from './ChatInput';

export interface ChatContainerProps {
  messages: ChatMessageData[];
  isQuerying: boolean;
  onSendMessage: (msg: string) => void;
  onCitationClick: (filename: string, page?: number) => void;
  onRetry?: () => void;
  className?: string;
}

export const ChatContainer: React.FC<ChatContainerProps> = ({
  messages,
  isQuerying,
  onSendMessage,
  onCitationClick,
  onRetry,
  className = '',
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView?.({ behavior: 'smooth' });
  }, [messages, isQuerying]);

  const isEmpty = messages.length === 0;

  return (
    <div className={`flex flex-col h-full bg-zinc-950 relative overflow-hidden ${className}`}>
      {/* Scrollable message area */}
      <div className="flex-1 overflow-y-auto px-2 sm:px-4 py-4 space-y-2">
        {isEmpty ? (
          <div className="h-full flex items-center justify-center">
            <EmptyHero onSelectPrompt={onSendMessage} />
          </div>
        ) : (
          <div className="max-w-4xl mx-auto w-full space-y-4">
            {messages.map((message) => (
              <ChatMessage
                key={message.id}
                message={message}
                onCitationClick={onCitationClick}
                onRetry={onRetry}
              />
            ))}

            {/* Querying loading indicator if no assistant message is pending */}
            {isQuerying && messages[messages.length - 1]?.role === 'user' && (
              <div className="flex justify-start my-4 px-4 animate-fade-in">
                <div className="flex items-start gap-3 max-w-full sm:max-w-4xl w-full">
                  <div className="w-8 h-8 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0 mt-1 shadow-[0_0_12px_rgba(35,134,54,0.15)]">
                    <Sparkles className="w-4 h-4 animate-pulse" />
                  </div>
                  <div className="flex items-center gap-2 px-4 py-3 rounded-2xl rounded-tl-sm bg-zinc-900/60 border border-white/[0.08] text-zinc-400 text-xs shadow-sm">
                    <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
                    <span>Đang truy xuất kiến thức và suy luận câu trả lời...</span>
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Fixed bottom chat input */}
      <div className="border-t border-white/[0.06] bg-zinc-950/80 backdrop-blur-md py-3 px-2 sm:px-4 shrink-0 z-10">
        <ChatInput
          onSendMessage={onSendMessage}
          isQuerying={isQuerying}
        />
      </div>
    </div>
  );
};

export default ChatContainer;
