import React from 'react';
import { AlertCircle, X } from 'lucide-react';

export interface SidebarErrorBannerProps {
  message: string;
  onDismiss: () => void;
}

const SidebarErrorBanner: React.FC<SidebarErrorBannerProps> = ({ message, onDismiss }) => (
  <div
    role="alert"
    className="mx-3 mb-2 p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-start justify-between gap-2 shadow-sm shrink-0"
  >
    <div className="flex items-start gap-2 min-w-0">
      <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
      <span className="text-[11px] leading-tight break-words">{message}</span>
    </div>
    <button
      type="button"
      onClick={onDismiss}
      aria-label="Dismiss sidebar error"
      className="text-rose-400 hover:text-rose-200 shrink-0 p-0.5 rounded transition-colors"
    >
      <X className="w-3.5 h-3.5" />
    </button>
  </div>
);

export default SidebarErrorBanner;
