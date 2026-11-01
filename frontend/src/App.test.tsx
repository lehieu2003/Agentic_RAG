import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from './App';

describe('App Split-Screen Workspace Integration', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    globalThis.fetch = vi.fn().mockImplementation((url: string, options?: any) => {
      const method = options?.method?.toUpperCase() || 'GET';

      if (url.includes('/api/v1/health')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ status: 'healthy', vector_store_count: 10 }),
        });
      }
      if (url.includes('/api/v1/files')) {
        if (method === 'DELETE') {
          return Promise.resolve({
            ok: true,
            json: async () => ({ status: 'deleted', filename: 'tài liệu máy bơm.pdf' }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({ files: [{ filename: 'tài liệu máy bơm.pdf', size: 1048576 }] }),
        });
      }
      if (url.includes('/api/v1/upload')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            filename: 'new_doc.pdf',
            status: 'indexed',
            chunks_indexed: 5,
          }),
        });
      }
      if (url.includes('/api/v1/query')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            answer: 'Reynolds Re = 228,571 theo công thức chuẩn.',
            citations: [{ filename: 'tài liệu máy bơm.pdf', page: 8 }],
            evidence: [
              {
                filename: 'tài liệu máy bơm.pdf',
                page: 8,
                score: 0.95,
                text: 'Công thức Re = rho * v * D / mu',
              },
            ],
            reasoning_steps: [{ node: 'retrieve', status: 'completed' }],
          }),
        });
      }
      return Promise.reject(new Error(`Unhandled URL ${url}`));
    });
  });

  it('loads health and files on mount', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/10 chunks/i)).toBeInTheDocument();
    });
  });

  it('clicking a citation badge opens document viewer at specified page', async () => {
    render(<App />);
    const textarea = screen.getByPlaceholderText(/Nhập câu hỏi kỹ thuật/i);
    fireEvent.change(textarea, { target: { value: 'Tính Reynolds' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });

    await waitFor(() => {
      expect(screen.getByText(/Reynolds Re = 228,571/i)).toBeInTheDocument();
    });

    const citationBadge = screen.getByText(/tài liệu máy bơm.pdf/i);
    fireEvent.click(citationBadge);

    await waitFor(() => {
      const iframe = screen.getByTitle('Document Preview') as HTMLIFrameElement;
      expect(iframe.src).toContain('#page=8');
    });
  });

  it('clicking prompt suggestion sends question to assistant', async () => {
    render(<App />);
    const promptCard = screen.getByRole('button', { name: /tính toán chuẩn số reynolds/i });
    fireEvent.click(promptCard);

    await waitFor(() => {
      expect(screen.getByText(/Reynolds Re = 228,571/i)).toBeInTheDocument();
    });
  });

  it('toggles sidebar and viewer from header buttons', async () => {
    render(<App />);
    await waitFor(() => {
      expect(screen.getByText(/10 chunks/i)).toBeInTheDocument();
    });

    // Sidebar should be closed initially
    expect(screen.queryByText(/Tài liệu đã lập chỉ mục/i)).not.toBeInTheDocument();

    // Toggle sidebar open
    fireEvent.click(screen.getByLabelText(/toggle sidebar/i));
    expect(screen.getByText(/Tài liệu đã lập chỉ mục/i)).toBeInTheDocument();

    // Toggle sidebar closed
    fireEvent.click(screen.getByLabelText(/toggle sidebar/i));
    expect(screen.queryByText(/Tài liệu đã lập chỉ mục/i)).not.toBeInTheDocument();

    // Toggle viewer
    fireEvent.click(screen.getByLabelText(/toggle document viewer/i));
    expect(screen.getByText(/Chưa chọn tài liệu/i)).toBeInTheDocument();
  });

  it('clears messages when new chat is clicked', async () => {
    render(<App />);
    const textarea = screen.getByPlaceholderText(/Nhập câu hỏi kỹ thuật/i);
    fireEvent.change(textarea, { target: { value: 'Tính Reynolds' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });

    await waitFor(() => {
      expect(screen.getByText(/Reynolds Re = 228,571/i)).toBeInTheDocument();
    });

    // Open sidebar to access new chat button
    fireEvent.click(screen.getByLabelText(/toggle sidebar/i));
    fireEvent.click(screen.getByRole('button', { name: /cuộc trò chuyện mới/i }));

    // EmptyHero should be back
    expect(screen.getByRole('button', { name: /tính toán chuẩn số reynolds/i })).toBeInTheDocument();
    expect(screen.queryByText(/Reynolds Re = 228,571/i)).not.toBeInTheDocument();
  });

  it('handles query error and retry button', async () => {
    // Override fetch once to simulate error
    let queryCallCount = 0;
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/health')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ status: 'healthy', vector_store_count: 10 }),
        });
      }
      if (url.includes('/api/v1/files')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ files: [] }),
        });
      }
      if (url.includes('/api/v1/query')) {
        queryCallCount++;
        if (queryCallCount === 1) {
          return Promise.resolve({
            ok: false,
            status: 500,
            statusText: 'Internal Server Error',
            json: async () => ({ detail: 'LLM service unavailable' }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({
            answer: 'Thử lại thành công.',
            citations: [],
          }),
        });
      }
      return Promise.reject(new Error(`Unhandled URL ${url}`));
    });

    render(<App />);
    const textarea = screen.getByPlaceholderText(/Nhập câu hỏi kỹ thuật/i);
    fireEvent.change(textarea, { target: { value: 'Lỗi kiểm tra' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });

    await waitFor(() => {
      expect(screen.getByText(/LLM service unavailable/i)).toBeInTheDocument();
    });

    // Click retry button
    const retryBtn = screen.getByRole('button', { name: /thử lại/i });
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(screen.getByText(/Thử lại thành công/i)).toBeInTheDocument();
    });
  });

  it('handles document deletion and updates state', async () => {
    render(<App />);
    // Open sidebar to see files list
    fireEvent.click(screen.getByLabelText(/toggle sidebar/i));
    await waitFor(() => {
      expect(screen.getByText('tài liệu máy bơm.pdf')).toBeInTheDocument();
    });

    const deleteBtn = screen.getByLabelText(/delete tài liệu máy bơm.pdf/i);
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(globalThis.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/files/t%C3%A0i%20li%E1%BB%87u%20m%C3%A1y%20b%C6%A1m.pdf'),
        expect.objectContaining({ method: 'DELETE' })
      );
    });
  });
});
