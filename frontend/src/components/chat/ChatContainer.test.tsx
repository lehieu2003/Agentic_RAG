import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ChatContainer from './ChatContainer';
import type { ChatMessageData } from '../../types';

describe('ChatContainer Component', () => {
  it('renders EmptyHero when messages list is empty and handles suggestion click', () => {
    const onSendMessage = vi.fn();
    render(
      <ChatContainer
        messages={[]}
        isQuerying={false}
        onSendMessage={onSendMessage}
        onCitationClick={vi.fn()}
      />
    );

    expect(screen.getByText(/Trợ lý Trí tuệ Tài liệu Kỹ thuật/i)).toBeInTheDocument();
    const promptCard = screen.getByRole('button', { name: /tính toán chuẩn số reynolds/i });
    fireEvent.click(promptCard);
    expect(onSendMessage).toHaveBeenCalledWith(
      'Tính toán chuẩn số Reynolds cho đường ống dẫn dầu D=150mm'
    );
  });

  it('renders messages and input correctly', () => {
    const messages: ChatMessageData[] = [
      { id: '1', role: 'user', content: 'Câu hỏi của tôi' },
      { id: '2', role: 'assistant', content: 'Câu trả lời của trợ lý' },
    ];
    render(
      <ChatContainer
        messages={messages}
        isQuerying={false}
        onSendMessage={vi.fn()}
        onCitationClick={vi.fn()}
      />
    );

    expect(screen.getByText('Câu hỏi của tôi')).toBeInTheDocument();
    expect(screen.getByText('Câu trả lời của trợ lý')).toBeInTheDocument();
    expect(screen.queryByText(/Trợ lý Trí tuệ Tài liệu Kỹ thuật/i)).not.toBeInTheDocument();
  });

  it('shows querying indicator when isQuerying is true and last message is user', () => {
    const messages: ChatMessageData[] = [
      { id: '1', role: 'user', content: 'Đang chờ xử lý' },
    ];
    render(
      <ChatContainer
        messages={messages}
        isQuerying={true}
        onSendMessage={vi.fn()}
        onCitationClick={vi.fn()}
      />
    );

    expect(
      screen.getByText(/Đang truy xuất kiến thức và suy luận câu trả lời/i)
    ).toBeInTheDocument();
  });

  it('passes onRetry to error messages', () => {
    const onRetry = vi.fn();
    const messages: ChatMessageData[] = [
      {
        id: '1',
        role: 'assistant',
        content: 'Có lỗi xảy ra',
        isError: true,
      },
    ];
    render(
      <ChatContainer
        messages={messages}
        isQuerying={false}
        onSendMessage={vi.fn()}
        onCitationClick={vi.fn()}
        onRetry={onRetry}
      />
    );

    const retryBtn = screen.getByRole('button', { name: /thử lại/i });
    fireEvent.click(retryBtn);
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
