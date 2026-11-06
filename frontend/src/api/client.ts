/**
 * Typed API client service connecting React frontend to FastAPI backend.
 */

import type {
  HealthResponse,
  FileInfo,
  FileListResponse,
  FileUploadResponse,
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
  const citations: Citation[] = (data.citations || []).map((c) => ({
    ...c,
    filename: c.filename ?? c.doc_name ?? '',
    doc_name: c.doc_name ?? c.filename ?? '',
    page: c.page ?? c.page_number,
    page_number: c.page_number ?? c.page,
  }));

  return {
    ...data,
    citations,
  };
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
