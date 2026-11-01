import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ChatInput from './ChatInput';

describe('ChatInput Component', () => {
  it('submits query when Enter key is pressed without Shift', () => {
    const onSendMessage = vi.fn();
    render(<ChatInput onSendMessage={onSendMessage} isQuerying={false} />);
    const textarea = screen.getByPlaceholderText(/Nhập câu hỏi kỹ thuật/i);
    fireEvent.change(textarea, { target: { value: 'Tính Reynolds' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    expect(onSendMessage).toHaveBeenCalledWith('Tính Reynolds');
  });

  it('does not submit when Shift+Enter is pressed', () => {
    const onSendMessage = vi.fn();
    render(<ChatInput onSendMessage={onSendMessage} isQuerying={false} />);
    const textarea = screen.getByPlaceholderText(/Nhập câu hỏi kỹ thuật/i);
    fireEvent.change(textarea, { target: { value: 'Tính Reynolds' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: true });
    expect(onSendMessage).not.toHaveBeenCalled();
  });

  it('does not submit empty query', () => {
    const onSendMessage = vi.fn();
    render(<ChatInput onSendMessage={onSendMessage} isQuerying={false} />);
    const textarea = screen.getByPlaceholderText(/Nhập câu hỏi kỹ thuật/i);
    fireEvent.change(textarea, { target: { value: '   ' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });
    expect(onSendMessage).not.toHaveBeenCalled();
  });

  it('submits when send button is clicked', () => {
    const onSendMessage = vi.fn();
    render(<ChatInput onSendMessage={onSendMessage} isQuerying={false} />);
    const textarea = screen.getByPlaceholderText(/Nhập câu hỏi kỹ thuật/i);
    fireEvent.change(textarea, { target: { value: 'Đường kính D=100' } });
    const sendButton = screen.getByRole('button', { name: /Gửi tin nhắn/i });
    fireEvent.click(sendButton);
    expect(onSendMessage).toHaveBeenCalledWith('Đường kính D=100');
  });

  it('disables input when isQuerying is true', () => {
    render(<ChatInput onSendMessage={vi.fn()} isQuerying={true} />);
    const textarea = screen.getByPlaceholderText(/Hệ thống đang xử lý/i);
    expect(textarea).toBeDisabled();
    const sendButton = screen.getByRole('button', { name: /Gửi tin nhắn/i });
    expect(sendButton).toBeDisabled();
  });
});
