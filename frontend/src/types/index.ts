/**
 * Core TypeScript definitions for Document Intelligence assistant.
 * Mirrors FastAPI backend schemas and UI state requirements.
 */

export interface HealthResponse {
  status: string;
  vector_store_count?: number;
  app_name?: string;
  retrieval_mode?: string;
  vector_store?: string;
  [key: string]: any;
}

export interface FileInfo {
  filename: string;
  size: number;
  size_bytes?: number;
  uploaded_at?: string;
  file_type?: string;
}

export interface FileListResponse {
  files: FileInfo[];
}

export interface FileUploadResponse {
  filename: string;
  pages_extracted?: number;
  pages_digital?: number;
  pages_scanned_ocr?: number;
  chunks_indexed?: number;
  status: string;
  message?: string;
}

export interface Citation {
  filename?: string;
  doc_name?: string;
  page?: number;
  page_number?: number;
}

export interface EvidenceChunk {
  id?: string;
  filename?: string;
  doc_name?: string;
  page?: number;
  page_number?: number;
  score?: number;
  text?: string;
  content?: string;
  metadata?: Record<string, any>;
  chunk?: {
    chunk_id?: string;
    doc_name?: string;
    page_number?: number;
    text?: string;
    metadata?: Record<string, any>;
  };
  [key: string]: any;
}

export interface ReasoningStep {
  node: string;
  status?: 'completed' | 'in_progress' | 'failed' | 'pending' | string;
  message?: string;
  details?: string;
}

export interface QAResponse {
  answer: string;
  citations: Citation[];
  evidence?: EvidenceChunk[];
  retrieved_chunks?: any[];
  reasoning_steps?: ReasoningStep[] | string[];
  abstained?: boolean;
  rewritten_queries?: string[];
  standalone_question?: string;
  session_id?: string;
}

export interface ChatMessageData {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  citations?: Citation[];
  evidence?: EvidenceChunk[];
  reasoning_steps?: ReasoningStep[];
  timestamp?: number;
  isError?: boolean;
  standalone_question?: string;
}

export interface SessionSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface SessionListResponse {
  sessions: SessionSummary[];
}

export interface SessionDetailResponse {
  session: SessionSummary;
  messages: Array<{
    role: 'user' | 'assistant';
    content: string;
    citations?: Citation[];
    reasoning_steps?: any[];
    created_at?: string;
    standalone_question?: string;
    id?: string;
  }>;
}
