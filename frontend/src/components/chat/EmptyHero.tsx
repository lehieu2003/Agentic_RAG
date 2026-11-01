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
      <div className="w-12 h-12 rounded-2xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400 mb-4 shadow-[0_0_24px_rgba(56,189,248,0.2)]">
        <Sparkles className="w-6 h-6" />
      </div>

      {/* Hero Title & Description */}
      <h2 className="text-2xl font-semibold text-white tracking-tight">
        Trợ lý Trí tuệ Tài liệu Kỹ thuật
      </h2>
      <p className="mt-2 text-sm text-zinc-400 max-w-lg leading-relaxed">
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
              className="bg-zinc-900/60 hover:bg-zinc-900/90 border border-white/[0.08] hover:border-sky-500/40 rounded-xl p-4 transition-all duration-200 shadow-sm hover:shadow-[0_8px_24px_rgba(0,0,0,0.5)] group text-left cursor-pointer flex flex-col justify-between relative overflow-hidden"
            >
              <div>
                <div className="flex items-center justify-between mb-2.5">
                  <span className="p-1.5 rounded-lg bg-white/[0.04] text-sky-400 border border-white/[0.08] group-hover:scale-105 transition-transform">
                    <Icon className="w-4 h-4" />
                  </span>
                  <span className="text-[10px] font-mono uppercase tracking-wider text-zinc-400 bg-white/[0.04] px-2 py-0.5 rounded border border-white/[0.06]">
                    {item.tag}
                  </span>
                </div>
                <h3 className="font-semibold text-sm text-zinc-100 group-hover:text-sky-400 transition-colors line-clamp-1">
                  {item.title}
                </h3>
                <p className="text-xs text-zinc-400 mt-1.5 leading-relaxed line-clamp-2">
                  {item.description}
                </p>
              </div>

              <div className="mt-4 flex items-center gap-1 text-[11px] font-medium text-sky-400 group-hover:translate-x-1 transition-transform">
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
