import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from './App';

describe('App Split-Screen Workspace Integration', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    localStorage.clear();
    globalThis.fetch = vi.fn().mockImplementation((url: string, options?: any) => {
      const method = options?.method?.toUpperCase() || 'GET';

      if (url.includes('/api/v1/health')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ status: 'ok', vector_store_count: 10 }),
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
      if (url.includes('/api/v1/sessions')) {
        if (method === 'DELETE') {
          return Promise.resolve({
            ok: true,
            json: async () => ({ status: 'deleted' }),
          });
        }
        if (url.match(/\/api\/v1\/sessions\/.+/)) {
          return Promise.resolve({
            ok: true,
            json: async () => ({
              session: { id: 's1', title: 'Tính Reynolds' },
              messages: [
                { role: 'user', content: 'Tính Reynolds của đường ống' },
                {
                  role: 'assistant',
                  content: 'Reynolds Re = 228,571.',
                  standalone_question: 'Tính chuẩn số Reynolds cho đường ống dẫn dầu',
                },
              ],
            }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({
            sessions: [
              { id: 's1', title: 'Tính Reynolds', created_at: '', updated_at: '' },
            ],
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
            session_id: 's1',
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
          json: async () => ({ status: 'ok', vector_store_count: 10 }),
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

  it('handles upload failure and displays error banner in sidebar', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/health')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ status: 'ok', vector_store_count: 10 }),
        });
      }
      if (url.includes('/api/v1/files')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ files: [] }),
        });
      }
      if (url.includes('/api/v1/upload')) {
        return Promise.resolve({
          ok: false,
          status: 400,
          statusText: 'Bad Request',
          json: async () => ({ detail: 'Tệp bị lỗi định dạng' }),
        });
      }
      return Promise.reject(new Error(`Unhandled URL ${url}`));
    });

    render(<App />);
    fireEvent.click(screen.getByLabelText(/toggle sidebar/i));

    const file = new File(['content'], 'test.pdf', { type: 'application/pdf' });
    const input = screen.getByTestId('file-upload-input');
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/Lỗi tải tệp: Tệp bị lỗi định dạng/i);
    });
  });

  it('handles delete failure and displays error banner in sidebar', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string, options?: any) => {
      const method = options?.method?.toUpperCase() || 'GET';
      if (url.includes('/api/v1/health')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ status: 'ok', vector_store_count: 10 }),
        });
      }
      if (url.includes('/api/v1/files')) {
        if (method === 'DELETE') {
          return Promise.resolve({
            ok: false,
            status: 500,
            statusText: 'Internal Server Error',
            json: async () => ({ detail: 'Không thể xóa tệp hệ thống' }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: async () => ({ files: [{ filename: 'loi_xoa.pdf', size: 1024 }] }),
        });
      }
      return Promise.reject(new Error(`Unhandled URL ${url}`));
    });

    render(<App />);
    fireEvent.click(screen.getByLabelText(/toggle sidebar/i));
    await waitFor(() => {
      expect(screen.getByText('loi_xoa.pdf')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText(/delete loi_xoa.pdf/i));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/Lỗi xóa tệp: Không thể xóa tệp hệ thống/i);
    });
  });

  it('correctly parses backend string reasoning steps and displays clean badges', async () => {
    globalThis.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/health')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ status: 'ok', vector_store_count: 10 }),
        });
      }
      if (url.includes('/api/v1/files')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ files: [] }),
        });
      }
      if (url.includes('/api/v1/query')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            answer: 'Đã hoàn tất quy trình suy luận.',
            citations: [],
            reasoning_steps: [
              '1. router: Nhận diện câu hỏi là phân tích kỹ thuật',
              '2. hybrid_retrieve: Tìm kiếm trong 10 đoạn tài liệu',
              '3. rerank: Tái xếp hạng kết quả',
              '4. grade_relevance: Đánh giá độ phù hợp',
              '5. generate: Tổng hợp câu trả lời chi tiết',
            ],
          }),
        });
      }
      return Promise.reject(new Error(`Unhandled URL ${url}`));
    });

    render(<App />);
    const textarea = screen.getByPlaceholderText(/Nhập câu hỏi kỹ thuật/i);
    fireEvent.change(textarea, { target: { value: 'Giải thích quy trình' } });
    fireEvent.keyDown(textarea, { key: 'Enter', shiftKey: false });

    await waitFor(() => {
      expect(screen.getByText(/Đã hoàn tất quy trình suy luận/i)).toBeInTheDocument();
    });

    // Expand reasoning steps
    fireEvent.click(screen.getByRole('button', { name: /Quy trình suy luận/i }));

    expect(screen.getByText(/Nhận diện câu hỏi là phân tích kỹ thuật/i)).toBeInTheDocument();
    expect(screen.getByText(/Tìm kiếm trong 10 đoạn tài liệu/i)).toBeInTheDocument();

    // Verify clean node badges
    expect(screen.getByText('router')).toBeInTheDocument();
    expect(screen.getByText('hybrid_retrieve')).toBeInTheDocument();
    expect(screen.getByText('rerank')).toBeInTheDocument();
    expect(screen.getByText('grade_relevance')).toBeInTheDocument();
    expect(screen.getByText('generate')).toBeInTheDocument();
  });

  it('fetches sessions on mount and displays them in sidebar', async () => {
    render(<App />);
    fireEvent.click(screen.getByLabelText(/toggle sidebar/i));
    await waitFor(() => {
      expect(screen.getByText('Tính Reynolds')).toBeInTheDocument();
    });
  });

  it('loads session messages when session is selected from sidebar', async () => {
    render(<App />);
    fireEvent.click(screen.getByLabelText(/toggle sidebar/i));
    await waitFor(() => {
      expect(screen.getByText('Tính Reynolds')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Tính Reynolds'));

    await waitFor(() => {
      expect(screen.getByText('Tính Reynolds của đường ống')).toBeInTheDocument();
      expect(screen.getByText('Reynolds Re = 228,571.')).toBeInTheDocument();
      expect(
        screen.getByText(/🔍 Đã hiểu ngữ cảnh: "Tính chuẩn số Reynolds cho đường ống dẫn dầu"/)
      ).toBeInTheDocument();
    });
  });

  it('restores active session from localStorage on mount', async () => {
    localStorage.setItem('doc_qa_active_session_id', 's1');
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Tính Reynolds của đường ống')).toBeInTheDocument();
      expect(screen.getByText('Reynolds Re = 228,571.')).toBeInTheDocument();
    });
  });

  it('deleting active session resets chat and clears localStorage', async () => {
    localStorage.setItem('doc_qa_active_session_id', 's1');
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Tính Reynolds của đường ống')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText(/toggle sidebar/i));
    const deleteBtn = screen.getByLabelText(/xóa cuộc trò chuyện/i);
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(screen.queryByText('Tính Reynolds của đường ống')).not.toBeInTheDocument();
      expect(screen.getByRole('button', { name: /tính toán chuẩn số reynolds/i })).toBeInTheDocument();
      expect(localStorage.getItem('doc_qa_active_session_id')).toBeNull();
    });
  });

  it('deleting all sessions resets chat and clears localStorage', async () => {
    localStorage.setItem('doc_qa_active_session_id', 's1');
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Tính Reynolds của đường ống')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText(/toggle sidebar/i));
    const deleteAllBtn = screen.getByLabelText(/xóa tất cả cuộc trò chuyện/i);
    fireEvent.click(deleteAllBtn);

    await waitFor(() => {
      expect(screen.queryByText('Tính Reynolds của đường ống')).not.toBeInTheDocument();
      expect(localStorage.getItem('doc_qa_active_session_id')).toBeNull();
    });
  });

  it('batch deleting active session resets chat and clears localStorage', async () => {
    localStorage.setItem('doc_qa_active_session_id', 's1');
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText('Tính Reynolds của đường ống')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText(/toggle sidebar/i));
    fireEvent.click(screen.getByLabelText(/chọn cuộc trò chuyện để xóa/i));

    fireEvent.click(screen.getByLabelText(/chọn Tính Reynolds/i));
    fireEvent.click(screen.getByRole('button', { name: /xóa đã chọn \(1\)/i }));

    await waitFor(() => {
      expect(screen.queryByText('Tính Reynolds của đường ống')).not.toBeInTheDocument();
      expect(localStorage.getItem('doc_qa_active_session_id')).toBeNull();
    });
  });
});
