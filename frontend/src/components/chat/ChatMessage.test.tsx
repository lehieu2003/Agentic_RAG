import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ChatMessage from './ChatMessage';
import type { ChatMessageData } from '../../types';

describe('ChatMessage Component', () => {
  it('renders markdown with math formula and clickable citation', () => {
    const onCitationClick = vi.fn();
    const message: ChatMessageData = {
      id: '1',
      role: 'assistant',
      content: 'Cột áp $H = 35\\text{ m}$, hiệu suất $\\eta = 80\\%$.',
      citations: [{ filename: 'tài liệu máy bơm.pdf', page: 11 }],
      timestamp: Date.now(),
    };

    render(<ChatMessage message={message} onCitationClick={onCitationClick} />);
    expect(screen.getByText(/tài liệu máy bơm.pdf/i)).toBeInTheDocument();
    expect(screen.getByText(/Trang 11/i)).toBeInTheDocument();

    fireEvent.click(screen.getByText(/tài liệu máy bơm.pdf/i));
    expect(onCitationClick).toHaveBeenCalledWith('tài liệu máy bơm.pdf', 11);
  });

  it('renders user message distinctively without citations container', () => {
    const onCitationClick = vi.fn();
    const message: ChatMessageData = {
      id: '2',
      role: 'user',
      content: 'Cho tôi biết thông số bơm ly tâm',
      timestamp: Date.now(),
    };

    render(<ChatMessage message={message} onCitationClick={onCitationClick} />);
    expect(screen.getByText('Cho tôi biết thông số bơm ly tâm')).toBeInTheDocument();
    expect(screen.queryByText(/Trang/i)).not.toBeInTheDocument();
  });

  it('renders reasoning steps and evidence when provided', () => {
    const onCitationClick = vi.fn();
    const message: ChatMessageData = {
      id: '3',
      role: 'assistant',
      content: 'Kết quả phân tích',
      reasoning_steps: [
        { node: 'retrieve', status: 'completed', message: 'Truy vấn 5 đoạn văn bản' },
        { node: 'grade', status: 'completed', message: 'Đánh giá độ liên quan 100%' },
      ],
      evidence: [
        {
          filename: 'pump_spec.pdf',
          page: 4,
          score: 0.92,
          text: 'Áp suất làm việc tối đa 16 bar',
        },
      ],
      timestamp: Date.now(),
    };

    render(<ChatMessage message={message} onCitationClick={onCitationClick} />);
    expect(screen.getByText('Kết quả phân tích')).toBeInTheDocument();
    expect(screen.getByText(/Quy trình suy luận/i)).toBeInTheDocument();
    expect(screen.getByText(/Dữ liệu trích dẫn/i)).toBeInTheDocument();
  });

  it('renders standalone_question context badge when query was reformulated', () => {
    const onCitationClick = vi.fn();
    const message: ChatMessageData = {
      id: '4',
      role: 'assistant',
      content: 'Lưu lượng định mức là 50 m3/h.',
      standalone_question: 'Lưu lượng định mức của bơm ly tâm là bao nhiêu?',
      timestamp: Date.now(),
    };

    render(<ChatMessage message={message} onCitationClick={onCitationClick} />);
    expect(
      screen.getByText(/🔍 Đã hiểu ngữ cảnh: "Lưu lượng định mức của bơm ly tâm là bao nhiêu\?"/)
    ).toBeInTheDocument();
  });

  it('does not render standalone_question badge when absent or identical', () => {
    const onCitationClick = vi.fn();
    const message: ChatMessageData = {
      id: '5',
      role: 'assistant',
      content: 'Câu trả lời trực tiếp.',
      timestamp: Date.now(),
    };

    render(<ChatMessage message={message} onCitationClick={onCitationClick} />);
    expect(screen.queryByText(/🔍 Đã hiểu ngữ cảnh:/)).not.toBeInTheDocument();
  });

  it('renders error state with retry button when isError is true', () => {
    const onCitationClick = vi.fn();
    const onRetry = vi.fn();
    const message: ChatMessageData = {
      id: '6',
      role: 'assistant',
      content: 'Đã xảy ra lỗi khi tạo phản hồi.',
      isError: true,
      timestamp: Date.now(),
    };

    render(
      <ChatMessage
        message={message}
        onCitationClick={onCitationClick}
        onRetry={onRetry}
      />
    );

    const retryBtn = screen.getByRole('button', { name: /Thử lại/i });
    expect(retryBtn).toBeInTheDocument();
    fireEvent.click(retryBtn);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('renders code block with copy button and handles copy click', async () => {
    const writeTextMock = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, {
      clipboard: {
        writeText: writeTextMock,
      },
    });

    const onCitationClick = vi.fn();
    const message: ChatMessageData = {
      id: '7',
      role: 'assistant',
      content: '```python\nprint("Hello World")\n```',
      timestamp: Date.now(),
    };

    render(<ChatMessage message={message} onCitationClick={onCitationClick} />);
    expect(screen.getByText('python')).toBeInTheDocument();
    expect(screen.getByText(/print\("Hello World"\)/)).toBeInTheDocument();

    const copyBtn = screen.getByRole('button', { name: /Sao chép mã/i });
    expect(copyBtn).toBeInTheDocument();
    fireEvent.click(copyBtn);

    await waitFor(() => {
      expect(writeTextMock).toHaveBeenCalled();
    });
  });
});
