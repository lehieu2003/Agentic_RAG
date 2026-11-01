import React from 'react';
import { PanelLeft, PanelRight, Sparkles, Activity } from 'lucide-react';
import type { HealthResponse } from '../../types';

export interface HeaderProps {
  isViewerOpen: boolean;
  onToggleViewer: () => void;
  isSidebarOpen: boolean;
  onToggleSidebar: () => void;
  health: HealthResponse | null;
}

export const Header: React.FC<HeaderProps> = ({
  isViewerOpen,
  onToggleViewer,
  isSidebarOpen: _isSidebarOpen,
  onToggleSidebar,
  health,
}) => {
  const isHealthy = health?.status === 'healthy';
  const isConnecting = health === null;
  const chunkCount = health?.vector_store_count ?? 0;

  return (
    <header className="h-14 border-b border-obsidian-border bg-obsidian-surface px-4 flex items-center justify-between select-none z-10 shrink-0">
      {/* Left branding & sidebar toggle */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onToggleSidebar}
          aria-label="Toggle sidebar"
          className="p-1.5 rounded-lg text-obsidian-text-muted hover:text-white hover:bg-obsidian-subtle border border-transparent hover:border-obsidian-border transition-colors focus:outline-none focus:ring-1 focus:ring-obsidian-accent"
        >
          <PanelLeft className="w-5 h-5" />
        </button>

        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
            <Sparkles className="w-4 h-4" />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm text-white tracking-tight">
                Document Intelligence
              </span>
              <span className="hidden sm:inline-block px-1.5 py-0.5 text-[10px] font-medium tracking-wide bg-obsidian-subtle text-obsidian-accent-blue border border-obsidian-border rounded">
                TCVN &amp; ISO Grounded
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Right status pill & viewer toggle */}
      <div className="flex items-center gap-3">
        {/* Status Pill */}
        <div className="flex items-center">
          {isHealthy ? (
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-medium bg-emerald-950/40 border border-emerald-800/60 text-emerald-300">
              <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>Sẵn sàng</span>
              <span className="text-emerald-500/80">•</span>
              <span>{chunkCount} chunks</span>
            </div>
          ) : isConnecting ? (
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-medium bg-amber-950/40 border border-amber-800/60 text-amber-300">
              <span className="h-2 w-2 rounded-full bg-amber-400 animate-pulse" />
              <span>Đang kết nối...</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-medium bg-rose-950/40 border border-rose-800/60 text-rose-300">
              <Activity className="w-3 h-3 text-rose-400" />
              <span>Mất kết nối</span>
            </div>
          )}
        </div>

        {/* Toggle Viewer Button */}
        <button
          type="button"
          onClick={onToggleViewer}
          aria-label="Toggle document viewer"
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors focus:outline-none focus:ring-1 focus:ring-obsidian-accent ${
            isViewerOpen
              ? 'bg-obsidian-subtle text-obsidian-accent-blue border-obsidian-border shadow-sm'
              : 'text-obsidian-text-muted hover:text-white hover:bg-obsidian-subtle border-transparent'
          }`}
          title="Xem tài liệu nguồn"
        >
          <PanelRight className="w-4 h-4" />
          <span className="hidden sm:inline">Tài liệu</span>
        </button>
      </div>
    </header>
  );
};

export default Header;
