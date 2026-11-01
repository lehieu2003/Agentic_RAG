import React from 'react';
import { Sparkles, Gauge, Compass, Activity, ArrowRight } from 'lucide-react';

export interface EmptyHeroProps {
  onSelectPrompt: (prompt: string) => void;
  className?: string;
}

interface PromptSuggestion {
  title: string;
  prompt: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  tag: string;
}

const SUGGESTIONS: PromptSuggestion[] = [
  {
    title: 'Tính toán chuẩn số Reynolds',
    prompt: 'Tính toán chuẩn số Reynolds cho đường ống dẫn dầu D=150mm',
    description: 'Xác định trạng thái chảy tầng hoặc chảy rối, công thức Re = ρvD/μ và hệ số ma sát Darcy.',
    icon: Gauge,
    tag: 'Thủy lực học',
  },
  {
    title: 'Thử nghiệm nghiệm thu máy bơm',
    prompt: 'Tiêu chuẩn nghiệm thu và thử nghiệm máy bơm ly tâm theo TCVN',
    description: 'Quy trình kiểm tra cột áp H, lưu lượng Q, công suất và dung sai chấp nhận kỹ thuật.',
    icon: Activity,
    tag: 'TCVN / Tiêu chuẩn',
  },
  {
    title: 'Lưu lượng thể tích qua tiết lưu',
    prompt: 'Công thức tính lưu lượng thể tích qua tiết lưu và tổn thất áp suất',
    description: 'Tính toán lưu lượng thể tích qua màng ngăn tiết lưu và độ sụt áp suất Δp.',
    icon: Compass,
    tag: 'Dòng chảy & Áp suất',
  },
];

export const EmptyHero: React.FC<EmptyHeroProps> = ({
  onSelectPrompt,
  className = '',
}) => {
  return (
    <div
      className={`flex flex-col items-center justify-center max-w-3xl mx-auto px-4 py-8 text-center select-none ${className}`}
    >
      {/* Hero Badge & Icon */}
      <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-4 shadow-[0_0_20px_rgba(35,134,54,0.2)]">
        <Sparkles className="w-6 h-6" />
      </div>

      {/* Hero Title & Description */}
      <h2 className="text-xl sm:text-2xl font-bold text-white tracking-tight">
        Trợ lý Trí tuệ Tài liệu Kỹ thuật
      </h2>
      <p className="mt-2 text-sm text-obsidian-text-muted max-w-lg leading-relaxed">
        Tra cứu tiêu chuẩn TCVN, ISO, tài liệu thiết kế cơ khí và hệ thống công nghiệp.
        Hỗ trợ giải toán kỹ thuật với công thức KaTeX và kiểm chứng nguồn gốc tài liệu.
      </p>

      {/* Suggested Prompts Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3 w-full mt-8 text-left">
        {SUGGESTIONS.map((item, idx) => {
          const Icon = item.icon;
          return (
            <button
              key={idx}
              type="button"
              onClick={() => onSelectPrompt(item.prompt)}
              className="group p-4 rounded-xl bg-obsidian-surface/80 hover:bg-obsidian-subtle border border-obsidian-border hover:border-obsidian-accent-blue/50 transition-all duration-200 text-left cursor-pointer flex flex-col justify-between hover:shadow-[0_4px_20px_rgba(0,0,0,0.3)] relative overflow-hidden"
            >
              <div>
                <div className="flex items-center justify-between mb-2.5">
                  <span className="p-1.5 rounded-lg bg-obsidian-subtle text-obsidian-accent-blue border border-obsidian-border group-hover:scale-105 transition-transform">
                    <Icon className="w-4 h-4" />
                  </span>
                  <span className="text-[10px] font-mono uppercase tracking-wider text-obsidian-text-muted bg-obsidian-bg/80 px-2 py-0.5 rounded border border-obsidian-border/50">
                    {item.tag}
                  </span>
                </div>
                <h3 className="font-semibold text-sm text-white group-hover:text-obsidian-accent-blue transition-colors line-clamp-1">
                  {item.title}
                </h3>
                <p className="text-xs text-obsidian-text-muted mt-1.5 leading-relaxed line-clamp-2">
                  {item.description}
                </p>
              </div>

              <div className="mt-4 flex items-center gap-1 text-[11px] font-medium text-obsidian-accent-blue group-hover:translate-x-1 transition-transform">
                <span>Đặt câu hỏi</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default EmptyHero;
