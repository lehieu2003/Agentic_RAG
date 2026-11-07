/**
 * Typed API client service connecting React frontend to FastAPI backend.
 */

import type {
  HealthResponse,
  FileInfo,
  FileListResponse,
  FileUploadResponse,
  IngestionJob,
  QAResponse,
  Citation,
  SessionSummary,
  SessionListResponse,
  SessionDetailResponse,
} from '../types';

const API_BASE = '/api/v1';

/**
 * Common response handler with error extraction.
 */
async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorMsg = res.statusText;
    if (typeof res.json === 'function') {
      try {
        const body = await res.json();
        if (body?.detail) {
          errorMsg = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
        } else if (body?.message) {
          errorMsg = body.message;
        }
      } catch {
        // Fallback to statusText on JSON parse error
      }
    }
    throw new Error(errorMsg || `Request failed with status ${res.status}`);
  }
  return res.json() as Promise<T>;
}

/**
 * Normalize citation field aliases (doc_name/filename, page/page_number).
 */
function normalizeQAResponse(data: QAResponse): QAResponse {
  const citations: Citation[] = (data.citations || []).map((c) => ({
    ...c,
    filename: c.filename ?? c.doc_name ?? '',
    doc_name: c.doc_name ?? c.filename ?? '',
    page: c.page ?? c.page_number,
    page_number: c.page_number ?? c.page,
  }));
  return { ...data, citations };
}

/**
 * Check backend service and vector store status.
 */
export async function checkHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  return handleResponse<HealthResponse>(res);
}

/**
 * Retrieve list of indexed documents.
 * Normalizes array or wrapped `{ files: [...] }` responses.
 */
export async function getFiles(): Promise<FileInfo[]> {
  const res = await fetch(`${API_BASE}/files`);
  const data = await handleResponse<FileInfo[] | FileListResponse>(res);
  const list: FileInfo[] = Array.isArray(data) ? data : (data.files || []);
  return list.map((item) => ({
    ...item,
    filename: item.filename,
    size: item.size ?? item.size_bytes ?? 0,
    size_bytes: item.size_bytes ?? item.size ?? 0,
  }));
}

/**
 * Upload a document file for OCR extraction and vector store indexing.
 */
export async function uploadDocument(file: File): Promise<FileUploadResponse> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    body: formData,
  });
  return handleResponse<FileUploadResponse>(res);
}

/**
 * Upload a document in the background: returns immediately with a job to poll.
 */
export async function uploadDocumentAsync(file: File): Promise<IngestionJob> {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch(`${API_BASE}/upload?mode=background`, {
    method: 'POST',
    body: formData,
  });
  return handleResponse<IngestionJob>(res);
}

/**
 * Fetch the current status of one background ingestion job.
 */
export async function getUploadJob(jobId: string): Promise<IngestionJob> {
  const res = await fetch(`${API_BASE}/upload/jobs/${encodeURIComponent(jobId)}`);
  return handleResponse<IngestionJob>(res);
}

const UPLOAD_JOB_TERMINAL: IngestionJob['status'][] = ['success', 'already_exists', 'failed'];

/**
 * Poll an ingestion job until it reaches a terminal state.
 * Rejects with the job's error detail when processing fails.
 */
export async function pollUploadJob(
  jobId: string,
  options: { intervalMs?: number; timeoutMs?: number } = {},
): Promise<IngestionJob> {
  const intervalMs = options.intervalMs ?? 1000;
  const timeoutMs = options.timeoutMs ?? 10 * 60 * 1000;
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    const job = await getUploadJob(jobId);
    if (job.status === 'failed') {
      throw new Error(job.error || 'Xử lý tài liệu thất bại.');
    }
    if (UPLOAD_JOB_TERMINAL.includes(job.status)) {
      return job;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error('Hết thời gian chờ xử lý tài liệu. Vui lòng thử lại sau.');
}

/**
 * Delete a document from vector index and physical disk.
 */
export async function deleteDocument(
  filename: string
): Promise<{ status: string; message?: string; [key: string]: any }> {
  const res = await fetch(`${API_BASE}/files/${encodeURIComponent(filename)}`, {
    method: 'DELETE',
  });
  return handleResponse(res);
}

/**
 * Query the assistant with a natural language question.
 */
export async function askQuestion(
  question: string,
  sessionId?: string | null
): Promise<QAResponse> {
  const res = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      question,
      session_id: sessionId || undefined,
    }),
  });

  const data = await handleResponse<QAResponse>(res);
  return normalizeQAResponse(data);
}

export interface AskStreamHandlers {
  /** Fired once the conversation session is resolved (before any step). */
  onSession?: (sessionId: string) => void;
  /** Fired per reasoning step as pipeline nodes complete. */
  onStep?: (step: string) => void;
}

/**
 * Query the assistant over the SSE endpoint, reporting progress via handlers.
 * Resolves with the same normalized QAResponse as {@link askQuestion}.
 * Throws when the stream is unavailable or the server reports an error.
 */
export async function askQuestionStream(
  question: string,
  sessionId: string | null | undefined,
  handlers: AskStreamHandlers = {},
): Promise<QAResponse> {
  const res = await fetch(`${API_BASE}/query/stream`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      question,
      session_id: sessionId || undefined,
    }),
  });

  const contentType = res.headers?.get?.('content-type') || '';
  if (!res.ok || !contentType.includes('text/event-stream') || !res.body) {
    throw new Error(`Streaming unavailable (status ${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let finalResponse: QAResponse | null = null;

  const handleBlock = (block: string): void => {
    let event = 'message';
    let data = '';
    for (const line of block.split('\n')) {
      if (line.startsWith('event: ')) {
        event = line.slice('event: '.length);
      } else if (line.startsWith('data: ')) {
        data = line.slice('data: '.length);
      }
    }
    if (!data) return;
    const payload = JSON.parse(data) as any;
    switch (event) {
      case 'session':
        handlers.onSession?.(payload.session_id);
        break;
      case 'reasoning':
        handlers.onStep?.(payload.step);
        break;
      case 'answer':
        finalResponse = normalizeQAResponse(payload.response as QAResponse);
        break;
      case 'error':
        throw new Error(payload.detail || 'Lỗi xử lý câu hỏi.');
      default:
        break;
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let separator = buffer.indexOf('\n\n');
    while (separator >= 0) {
      handleBlock(buffer.slice(0, separator));
      buffer = buffer.slice(separator + 2);
      separator = buffer.indexOf('\n\n');
    }
  }
  if (buffer.trim()) {
    handleBlock(buffer);
  }

  if (!finalResponse) {
    throw new Error('Stream kết thúc nhưng không nhận được câu trả lời.');
  }
  return finalResponse;
}

/**
 * List all chat sessions ordered by last active.
 */
export async function listSessions(): Promise<SessionSummary[]> {
  const res = await fetch(`${API_BASE}/sessions`);
  const data = await handleResponse<SessionSummary[] | SessionListResponse>(res);
  return Array.isArray(data) ? data : (data.sessions || []);
}

/**
 * Retrieve session details and history messages.
 */
export async function getSession(sessionId: string): Promise<SessionDetailResponse> {
  const res = await fetch(`${API_BASE}/sessions/${encodeURIComponent(sessionId)}`);
  return handleResponse<SessionDetailResponse>(res);
}

/**
 * Delete a session and its associated message history.
 */
export async function deleteSession(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
  });
  await handleResponse<{ status: string; [key: string]: any }>(res);
}

/**
 * Delete all chat sessions and message histories.
 */
export async function deleteAllSessions(): Promise<{ status: string; deleted_count: number; message?: string }> {
  const res = await fetch(`${API_BASE}/sessions`, {
    method: 'DELETE',
  });
  return handleResponse<{ status: string; deleted_count: number; message?: string }>(res);
}

/**
 * Delete multiple chat sessions by their IDs.
 */
export async function deleteSessionsBatch(
  sessionIds: string[]
): Promise<{ status: string; deleted_count: number; message?: string }> {
  const res = await fetch(`${API_BASE}/sessions/batch-delete`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ session_ids: sessionIds }),
  });
  return handleResponse<{ status: string; deleted_count: number; message?: string }>(res);
}

/**
 * Build browser streaming URL for a document with page anchor support.
 */
export function getDocumentStreamUrl(filename: string, page?: number): string {
  const encodedName = encodeURIComponent(filename);
  const pageHash = page ? `#page=${page}` : '';
  return `${API_BASE}/files/${encodedName}${pageHash}`;
}
