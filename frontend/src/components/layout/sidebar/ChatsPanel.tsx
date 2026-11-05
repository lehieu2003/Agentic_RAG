import React, { useState } from 'react';
import { Plus, Trash2, MessageSquare, CheckSquare } from 'lucide-react';
import type { SessionSummary } from '../../../types';
import { formatSessionDate } from './utils';

export interface ChatsPanelProps {
  isActive: boolean;
  onNewChat: () => void;
  sessions?: SessionSummary[];
  activeSessionId?: string | null;
  onSelectSession?: (id: string) => void;
  onDeleteSession?: (id: string) => Promise<void>;
  onDeleteAllSessions?: () => Promise<void> | void;
  onDeleteSessions?: (sessionIds: string[]) => Promise<void> | void;
}

const ChatsPanel: React.FC<ChatsPanelProps> = ({
  isActive,
  onNewChat,
  sessions = [],
  activeSessionId = null,
  onSelectSession,
  onDeleteSession,
  onDeleteAllSessions,
  onDeleteSessions,
}) => {
  const [isSelectMode, setIsSelectMode] = useState(false);
  const [selectedSessionIds, setSelectedSessionIds] = useState<Set<string>>(new Set());

  const toggleSelectSession = (id: string) => {
    setSelectedSessionIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (selectedSessionIds.size === sessions.length) {
      setSelectedSessionIds(new Set());
    } else {
      setSelectedSessionIds(new Set(sessions.map((s) => s.id)));
    }
  };

  const handleDeleteAllSessions = () => {
    const confirmed = window.confirm(
      'Bạn có chắc chắn muốn xóa tất cả cuộc trò chuyện không?'
    );
    if (confirmed) {
      onDeleteAllSessions?.();
    }
  };

  const handleDeleteSelected = () => {
    const count = selectedSessionIds.size;
    if (count === 0) return;
    const confirmed = window.confirm(
      `Bạn có chắc chắn muốn xóa ${count} cuộc trò chuyện đã chọn không?`
    );
    if (confirmed) {
      onDeleteSessions?.(Array.from(selectedSessionIds));
      setIsSelectMode(false);
      setSelectedSessionIds(new Set());
    }
  };

  return (
    <div
      id="panel-chats"
      role="tabpanel"
      aria-labelledby="tab-chats"
      className={isActive ? 'flex flex-col flex-1 min-h-0' : 'hidden'}
    >
      {/* New Chat Button */}
      <div className="p-3 border-b border-white/[0.06] shrink-0">
        <button
          type="button"
          onClick={onNewChat}
          className="w-full bg-sky-500/10 hover:bg-sky-500/20 text-sky-400 border border-sky-500/30 hover:border-sky-400/50 rounded-xl py-2 px-3 text-xs font-medium flex items-center justify-center gap-2 transition-all shadow-sm active:scale-[0.99]"
        >
          <Plus className="w-4 h-4" />
          <span>Cuộc trò chuyện mới</span>
        </button>
      </div>

      {/* Chat sessions header or selection toolbar */}
      {isSelectMode ? (
        <div className="px-3 pt-3 pb-2 flex items-center justify-between gap-1.5 border-b border-white/[0.06] bg-zinc-900/60 shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <label className="flex items-center gap-1.5 text-xs text-zinc-300 cursor-pointer">
              <input
                type="checkbox"
                aria-label="Chọn tất cả"
                checked={sessions.length > 0 && selectedSessionIds.size === sessions.length}
                onChange={toggleSelectAll}
                className="w-3.5 h-3.5 rounded bg-zinc-800 border-white/[0.2] text-sky-500 focus:ring-sky-400 focus:ring-offset-0 cursor-pointer accent-sky-500"
              />
              <span className="text-[11px] font-medium text-zinc-300 whitespace-nowrap">
                Đã chọn {selectedSessionIds.size}
              </span>
            </label>
          </div>

          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={handleDeleteSelected}
              disabled={selectedSessionIds.size === 0}
              aria-label={`Xóa đã chọn (${selectedSessionIds.size})`}
              className={`text-[11px] px-2 py-0.5 rounded-lg font-medium transition-all flex items-center gap-1 ${
                selectedSessionIds.size > 0
                  ? 'bg-rose-500/20 text-rose-300 hover:bg-rose-500/30 border border-rose-500/30 shadow-sm cursor-pointer'
                  : 'bg-white/[0.04] text-zinc-500 border border-white/[0.06] cursor-not-allowed opacity-50'
              }`}
            >
              <Trash2 className="w-3 h-3" />
              <span>Xóa đã chọn ({selectedSessionIds.size})</span>
            </button>
            <button
              type="button"
              onClick={() => {
                setIsSelectMode(false);
                setSelectedSessionIds(new Set());
              }}
              aria-label="Hủy chọn"
              className="text-[11px] px-2 py-0.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.06] transition-colors"
            >
              Hủy
            </button>
          </div>
        </div>
      ) : (
        <div className="px-3 pt-3 pb-2 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-zinc-300">
            <MessageSquare className="w-3.5 h-3.5 text-zinc-400" />
            <span>Cuộc trò chuyện gần đây</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-zinc-400 mr-0.5">
              {sessions.length}
            </span>
            {sessions.length > 0 && (
              <>
                <button
                  type="button"
                  onClick={() => {
                    setIsSelectMode(true);
                    setSelectedSessionIds(new Set());
                  }}
                  aria-label="Chọn cuộc trò chuyện để xóa"
                  title="Chọn nhiều để xóa"
                  className="p-1 rounded-md text-zinc-400 hover:text-sky-300 hover:bg-white/[0.06] transition-colors"
                >
                  <CheckSquare className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  onClick={handleDeleteAllSessions}
                  aria-label="Xóa tất cả cuộc trò chuyện"
                  title="Xóa tất cả cuộc trò chuyện"
                  className="p-1 rounded-md text-zinc-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </>
            )}
          </div>
        </div>
      )}

      {/* Sessions List */}
      <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-1.5 min-h-0">
        {sessions.length === 0 ? (
          <div className="text-center py-8 text-zinc-500">
            <MessageSquare className="w-8 h-8 mx-auto mb-2 opacity-30" />
            <p className="text-xs">Chưa có cuộc trò chuyện nào</p>
            <p className="text-[10px] mt-1 text-zinc-600">
              Bắt đầu một câu hỏi mới để lưu vào đây
            </p>
          </div>
        ) : (
          sessions.map((session) => {
            const isActive = activeSessionId === session.id;
            const isSelected = selectedSessionIds.has(session.id);
            return (
              <div
                key={session.id}
                onClick={() => {
                  if (isSelectMode) {
                    toggleSelectSession(session.id);
                  } else {
                    onSelectSession?.(session.id);
                  }
                }}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    if (isSelectMode) {
                      toggleSelectSession(session.id);
                    } else {
                      onSelectSession?.(session.id);
                    }
                  }
                }}
                className={`group flex items-center justify-between p-2.5 rounded-xl border text-xs cursor-pointer transition-all ${
                  isSelectMode && isSelected
                    ? 'bg-sky-500/10 border-sky-500/40 text-white shadow-sm'
                    : isActive && !isSelectMode
                    ? 'bg-white/[0.06] text-white border-l-2 border-sky-400 border-white/[0.08] shadow-sm font-medium'
                    : 'bg-zinc-900/30 hover:bg-white/[0.04] border-white/[0.04] hover:border-white/[0.08] text-zinc-400 hover:text-zinc-200'
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0 pr-2">
                  {isSelectMode ? (
                    <input
                      type="checkbox"
                      aria-label={`Chọn ${session.title || 'Cuộc trò chuyện'}`}
                      checked={isSelected}
                      onClick={(e) => {
                        e.stopPropagation();
                      }}
                      onChange={() => {
                        toggleSelectSession(session.id);
                      }}
                      className="w-3.5 h-3.5 rounded bg-zinc-800 border-white/[0.2] text-sky-500 focus:ring-sky-400 cursor-pointer accent-sky-500 shrink-0"
                    />
                  ) : (
                    <MessageSquare
                      className={`w-3.5 h-3.5 shrink-0 ${
                        isActive ? 'text-sky-400' : 'text-zinc-500 group-hover:text-zinc-300'
                      }`}
                    />
                  )}
                  <div className="flex flex-col min-w-0">
                    <span className="truncate font-medium text-xs leading-tight" title={session.title}>
                      {session.title || 'Cuộc trò chuyện'}
                    </span>
                    {(session.updated_at || session.created_at) && (
                      <span className="text-[10px] text-zinc-500 mt-0.5">
                        {formatSessionDate(session.updated_at || session.created_at)}
                      </span>
                    )}
                  </div>
                </div>

                {!isSelectMode && (
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      const confirmed = window.confirm(
                        'Bạn có chắc chắn muốn xóa cuộc trò chuyện này không?'
                          );
                          if (confirmed) {
                            onDeleteSession?.(session.id);
                          }
                        }}
                        aria-label="Xóa cuộc trò chuyện"
                        title="Xóa cuộc trò chuyện"
                        className="p-1 rounded-lg text-zinc-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors shrink-0 opacity-80 md:opacity-0 md:group-hover:opacity-100 md:focus:opacity-100"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>
  );
};

export default ChatsPanel;
