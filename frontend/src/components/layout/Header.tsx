import React from 'react';
import { Moon, PanelLeft, PanelRight, Sparkles, Sun } from 'lucide-react';
import type { HealthResponse } from '../../types';
import { useTheme } from '../../hooks/useTheme';

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
  const isHealthy = health?.status === 'ok';
  const isConnecting = health === null;
  const chunkCount = health?.vector_store_count ?? 0;
  const { theme, toggleTheme } = useTheme();
  const isLight = theme === 'light';

  return (
    <header className="h-[52px] sticky top-0 bg-zinc-950/80 backdrop-blur-md border-b border-white/[0.06] px-4 flex items-center justify-between select-none z-10 shrink-0">
      {/* Left branding & sidebar toggle */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onToggleSidebar}
          aria-label="Toggle sidebar"
          className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.06] border border-transparent hover:border-white/[0.08] transition-colors focus:outline-none focus:ring-1 focus:ring-sky-500/50"
          title="Đóng / mở danh mục"
        >
          <PanelLeft className="w-4 h-4" />
        </button>

        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 shadow-[0_0_12px_rgba(56,189,248,0.15)]">
            <Sparkles className="w-4 h-4" />
          </div>
          <div className="flex items-center gap-2">
            <span className="font-semibold text-sm text-white tracking-tight">
              Document Intelligence
            </span>
            <span className="hidden sm:inline-block text-zinc-600 text-xs">/</span>
            <span className="hidden sm:inline-block text-[10px] font-mono px-2 py-0.5 rounded-full bg-white/[0.04] border border-white/[0.08] text-zinc-400">
              TCVN &amp; ISO Grounded
            </span>
          </div>
        </div>
      </div>

      {/* Right status pill & viewer toggle */}
      <div className="flex items-center gap-3">
        {/* Status Pill */}
        <div className="flex items-center">
          {isHealthy ? (
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-medium bg-zinc-900/80 border border-white/[0.08] text-zinc-300">
              <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.6)] animate-pulse" />
              <span>Sẵn sàng</span>
              <span className="text-zinc-600">•</span>
              <span>{chunkCount.toLocaleString()} chunks</span>
            </div>
          ) : isConnecting ? (
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-medium bg-zinc-900/80 border border-white/[0.08] text-zinc-300">
              <span className="h-2 w-2 rounded-full bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.6)] animate-pulse" />
              <span>Đang kết nối...</span>
            </div>
          ) : (
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-full text-xs font-medium bg-zinc-900/80 border border-white/[0.08] text-zinc-300">
              <span className="h-2 w-2 rounded-full bg-rose-400 shadow-[0_0_8px_rgba(244,63,94,0.6)]" />
              <span>Mất kết nối</span>
            </div>
          )}
        </div>

        {/* Theme Toggle */}
        <button
          type="button"
          onClick={toggleTheme}
          aria-label={isLight ? 'Chuyển sang giao diện tối' : 'Chuyển sang giao diện sáng'}
          aria-pressed={isLight}
          className="p-1.5 rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.06] border border-transparent hover:border-white/[0.08] transition-colors focus:outline-none focus:ring-1 focus:ring-sky-500/50"
          title={isLight ? 'Giao diện tối' : 'Giao diện sáng'}
        >
          {isLight ? <Moon className="w-4 h-4" /> : <Sun className="w-4 h-4" />}
        </button>

        {/* Toggle Viewer Button */}
        <button
          type="button"
          onClick={onToggleViewer}
          aria-label="Toggle document viewer"
          className={`flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium border transition-colors focus:outline-none focus:ring-1 focus:ring-sky-500/50 ${
            isViewerOpen
              ? 'bg-white/[0.08] text-sky-400 border-white/[0.1] shadow-sm'
              : 'text-zinc-400 hover:text-white hover:bg-white/[0.06] border-transparent hover:border-white/[0.08]'
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
