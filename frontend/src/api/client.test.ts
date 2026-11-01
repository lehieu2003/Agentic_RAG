import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  checkHealth,
  getFiles,
  uploadDocument,
  deleteDocument,
  askQuestion,
  getDocumentStreamUrl,
  listSessions,
  getSession,
  deleteSession,
} from './client';

describe('ApiClient Service', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('checkHealth returns backend status', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'healthy', vector_store_count: 42 }),
    } as Response);

    const res = await checkHealth();
    expect(res.status).toBe('healthy');
    expect(res.vector_store_count).toBe(42);
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/v1/health');
  });

  it('getFiles returns normalized file list from array response', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        { filename: 'doc1.pdf', size_bytes: 1024, uploaded_at: '2026-11-01T00:00:00Z', file_type: '.pdf' }
      ],
    } as Response);

    const res = await getFiles();
    expect(res).toHaveLength(1);
    expect(res[0].filename).toBe('doc1.pdf');
    expect(res[0].size).toBe(1024);
    expect(res[0].size_bytes).toBe(1024);
    expect(globalThis.fetch).toHaveBeenCalledWith('/api/v1/files');
  });

  it('getFiles handles object with files array', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        files: [{ filename: 'doc2.docx', size: 2048 }]
      }),
    } as Response);

    const res = await getFiles();
    expect(res).toHaveLength(1);
    expect(res[0].filename).toBe('doc2.docx');
    expect(res[0].size).toBe(2048);
  });

  it('uploadDocument uploads file via FormData to /api/v1/upload', async () => {
    const mockFile = new File(['content'], 'test.pdf', { type: 'application/pdf' });
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        filename: 'test.pdf',
        pages_extracted: 10,
        pages_digital: 8,
        pages_scanned_ocr: 2,
        chunks_indexed: 35,
        status: 'success',
      }),
    } as Response);

    const res = await uploadDocument(mockFile);
    expect(res.filename).toBe('test.pdf');
    expect(res.status).toBe('success');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/upload',
      expect.objectContaining({
        method: 'POST',
        body: expect.any(FormData),
      })
    );
  });

  it('deleteDocument sends DELETE request to encoded file URL', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        status: 'success',
        filename: 'tài liệu.pdf',
        file_deleted: true,
        chunks_removed: 15,
      }),
    } as Response);

    const res = await deleteDocument('tài liệu.pdf');
    expect(res.status).toBe('success');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      `/api/v1/files/${encodeURIComponent('tài liệu.pdf')}`,
      expect.objectContaining({
        method: 'DELETE',
      })
    );
  });

  it('getDocumentStreamUrl encodes Vietnamese filenames and appends page hash', () => {
    const url = getDocumentStreamUrl('tài liệu máy bơm.pdf', 11);
    expect(url).toContain(encodeURIComponent('tài liệu máy bơm.pdf'));
    expect(url).toContain('#page=11');
    expect(url).toBe(`/api/v1/files/${encodeURIComponent('tài liệu máy bơm.pdf')}#page=11`);
  });

  it('getDocumentStreamUrl returns stream URL without page hash when page is omitted', () => {
    const url = getDocumentStreamUrl('doc.pdf');
    expect(url).toBe(`/api/v1/files/doc.pdf`);
  });

  it('askQuestion sends question and top_k to /api/v1/query', async () => {
    const mockQA = {
      answer: 'Reynolds Re = 228,571',
      citations: [{ filename: 'test.pdf', page: 8 }],
      evidence: [],
      reasoning_steps: [{ node: 'retrieve', status: 'completed' }],
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockQA,
    } as Response);

    const res = await askQuestion('Tính Reynolds', 10);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/query',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: 'Tính Reynolds', top_k: 10 }),
      })
    );
    expect(res.answer).toBe('Reynolds Re = 228,571');
    expect(res.citations).toHaveLength(1);
    expect(res.citations[0].filename).toBe('test.pdf');
    expect(res.citations[0].page).toBe(8);
  });

  it('askQuestion defaults top_k to 8 when not provided', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        answer: 'Test answer',
        citations: [],
      }),
    } as Response);

    await askQuestion('Default top_k test');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/api/v1/query',
      expect.objectContaining({
        body: JSON.stringify({ question: 'Default top_k test', top_k: 8 }),
      })
    );
  });

  it('throws friendly error on network failure', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      statusText: 'Service Unavailable',
    } as Response);

    await expect(askQuestion('fail')).rejects.toThrow('Service Unavailable');
  });

  it('extracts detail message from error response json when present', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      statusText: 'Bad Request',
      json: async () => ({ detail: 'Corrupted or unreadable document' }),
    } as Response);

    await expect(uploadDocument(new File([], 'bad.pdf'))).rejects.toThrow('Corrupted or unreadable document');
  });

  describe('Session API Client', () => {
    it('listSessions fetches session summaries', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          sessions: [{ id: 's1', title: 'Máy bơm', created_at: '2026-11-01T00:00:00Z', updated_at: '2026-11-01T00:00:00Z' }],
        }),
      } as Response);

      const res = await listSessions();
      expect(res).toHaveLength(1);
      expect(res[0].id).toBe('s1');
      expect(res[0].title).toBe('Máy bơm');
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/v1/sessions');
    });

    it('listSessions handles direct array response', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [
          { id: 's2', title: 'Session 2', created_at: '', updated_at: '' }
        ],
      } as Response);

      const res = await listSessions();
      expect(res).toHaveLength(1);
      expect(res[0].id).toBe('s2');
    });

    it('getSession fetches session detail with encoded session ID', async () => {
      const mockDetail = {
        session: { id: 's 1/special', title: 'Test Session', created_at: '', updated_at: '' },
        messages: [
          { role: 'user', content: 'Xin chào', created_at: '' },
          { role: 'assistant', content: 'Chào bạn', created_at: '' }
        ],
      };
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockDetail,
      } as Response);

      const res = await getSession('s 1/special');
      expect(res.session.id).toBe('s 1/special');
      expect(res.messages).toHaveLength(2);
      expect(globalThis.fetch).toHaveBeenCalledWith(
        `/api/v1/sessions/${encodeURIComponent('s 1/special')}`
      );
    });

    it('deleteSession sends DELETE to /api/v1/sessions/{id}', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: 'success' }),
      } as Response);

      await deleteSession('s 1/special');
      expect(globalThis.fetch).toHaveBeenCalledWith(
        `/api/v1/sessions/${encodeURIComponent('s 1/special')}`,
        expect.objectContaining({ method: 'DELETE' })
      );
    });

    it('askQuestion passes session_id when provided', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          answer: 'Câu trả lời tiếp nối',
          citations: [],
          session_id: 'sess-123',
          standalone_question: 'Câu hỏi độc lập',
        }),
      } as Response);

      const res = await askQuestion('Câu hỏi 2', 5, 'sess-123');
      expect(globalThis.fetch).toHaveBeenCalledWith(
        '/api/v1/query',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ question: 'Câu hỏi 2', top_k: 5, session_id: 'sess-123' }),
        })
      );
      expect(res.session_id).toBe('sess-123');
      expect(res.standalone_question).toBe('Câu hỏi độc lập');
    });

    it('askQuestion omits session_id when null or undefined', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          answer: 'Câu trả lời mới',
          citations: [],
        }),
      } as Response);

      await askQuestion('Câu hỏi mới', 8, null);
      expect(globalThis.fetch).toHaveBeenCalledWith(
        '/api/v1/query',
        expect.objectContaining({
          method: 'POST',
          body: JSON.stringify({ question: 'Câu hỏi mới', top_k: 8 }),
        })
      );
    });
  });
});
