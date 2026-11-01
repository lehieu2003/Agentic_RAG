import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import EmptyHero from './EmptyHero';

describe('EmptyHero Component', () => {
  it('renders hero title and prompt suggestions', () => {
    const handleSelectPrompt = vi.fn();
    render(<EmptyHero onSelectPrompt={handleSelectPrompt} />);

    expect(screen.getByText(/Trợ lý Trí tuệ Tài liệu Kỹ thuật/i)).toBeInTheDocument();
    expect(screen.getByText(/Tính toán chuẩn số Reynolds/i)).toBeInTheDocument();
    expect(screen.getByText(/Thử nghiệm nghiệm thu máy bơm/i)).toBeInTheDocument();
    expect(screen.getByText(/Lưu lượng thể tích qua tiết lưu/i)).toBeInTheDocument();
  });

  it('triggers onSelectPrompt when a prompt card is clicked', () => {
    const handleSelectPrompt = vi.fn();
    render(<EmptyHero onSelectPrompt={handleSelectPrompt} />);

    const reynoldsBtn = screen.getByText(/Tính toán chuẩn số Reynolds/i).closest('button');
    expect(reynoldsBtn).toBeInTheDocument();
    fireEvent.click(reynoldsBtn!);

    expect(handleSelectPrompt).toHaveBeenCalledWith(
      'Tính toán chuẩn số Reynolds cho đường ống dẫn dầu D=150mm'
    );
  });
});
