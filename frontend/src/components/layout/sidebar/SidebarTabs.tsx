import React from 'react';
import { MessageSquare, Files } from 'lucide-react';

export interface SidebarTabsProps {
  activeTab: 'chats' | 'documents';
  onChange: (tab: 'chats' | 'documents') => void;
}

const SidebarTabs: React.FC<SidebarTabsProps> = ({ activeTab, onChange }) => (
  <div
    role="tablist"
    aria-label="Chuyển đổi danh mục"
    className="bg-zinc-900/90 border border-white/[0.08] p-1 rounded-xl flex gap-1 mx-3 my-2 shrink-0"
  >
    <button
      id="tab-chats"
      type="button"
      onClick={() => onChange('chats')}
      className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg text-xs transition-all ${
        activeTab === 'chats'
          ? 'bg-white/[0.08] text-white shadow-sm font-medium'
          : 'text-zinc-400 hover:text-white'
      }`}
      role="tab"
      aria-selected={activeTab === 'chats'}
      aria-controls="panel-chats"
    >
      <MessageSquare className="w-3.5 h-3.5" />
      <span>Cuộc trò chuyện</span>
    </button>
    <button
      id="tab-documents"
      type="button"
      onClick={() => onChange('documents')}
      className={`flex-1 flex items-center justify-center gap-1.5 py-1.5 px-3 rounded-lg text-xs transition-all ${
        activeTab === 'documents'
          ? 'bg-white/[0.08] text-white shadow-sm font-medium'
          : 'text-zinc-400 hover:text-white'
      }`}
      role="tab"
      aria-selected={activeTab === 'documents'}
      aria-controls="panel-documents"
    >
      <Files className="w-3.5 h-3.5" />
      <span>Tài liệu</span>
    </button>
  </div>
);

export default SidebarTabs;
