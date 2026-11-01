# React Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify a developer-grade, modern React Single-Page Application (SPA) in `frontend/` featuring a split-screen workspace (chat assistant + interactive document viewer) with KaTeX math rendering and one-click citation page synchronization, consuming the existing FastAPI backend with zero backend regressions.

**Architecture:** Vite + React 18/19 (TypeScript) + Tailwind CSS + Lucide React + react-markdown/KaTeX + PDF embed controller. The frontend communicates with the FastAPI backend over REST (`/api/v1/*`) via a Vite proxy during development and direct CORS calls in production.

**Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS, Lucide React, react-markdown, remark-math, rehype-katex, remark-gfm, Vitest, @testing-library/react, jsdom.

**Spec:** `file:///Users/lehieu/.gemini/antigravity/brain/089dae59-600e-4f43-beaf-f7beb6962f6a/react_frontend_design_spec.md`

## Global Constraints

- **Backend Invariance:** Zero breaking changes or regressions to existing FastAPI endpoints (`/api/v1/health`, `/api/v1/files`, `/api/v1/upload`, `/api/v1/files/{filename}`, `/api/v1/query`). Existing 112 pytest backend tests must remain 100% passing.
- **Node & NPM:** Built and tested with Node v24.21.0 and npm 11.19.0.
- **Design & Theme:** Strict Obsidian/Slate dark mode (#0d1117 / #161b22 / #21262d), Linear/Cursor minimalism, zero tacky AI-generated glow effects or low-contrast text.
- **Citation Sync:** Clicking any citation badge `[Tài liệu: doc.pdf, Trang 11]` must immediately open `doc.pdf` in the right pane and navigate to Page 11 using `#page=11`.
- **Math Rendering:** All formulas ($H$, $\eta$, $Re$, fractions, exponents) must render using KaTeX via `remark-math` and `rehype-katex`.
- **Git Safety:** Always prefix Git operations with `DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null`.

## Review Focus

1. **Filenames with spaces and Vietnamese unicode (e.g. `tài liệu máy bơm.pdf`):** URL encoding must be strictly handled using `encodeURIComponent(filename)` when constructing document streaming URLs to prevent broken 404s.
2. **Missing or Deleted Document Citations:** When a citation references a file that has been deleted or cannot be loaded, DocumentViewer must display an informative error state rather than a blank or crashed iframe.
3. **Backend Outage / 503 GRPC Error:** When FastAPI returns an error status (500 or 503) on `/api/v1/query`, the chat must render an inline error message card with a retry option without clearing user conversation history.
4. **Complex LaTeX Expressions:** Multiline formulas and inline math with fractions (`\frac{U \cdot D}{\nu}`) or Greek letters (`\eta`, `\rho`) must render without KaTeX crashing the component tree (strict: false / error boundary).
5. **Non-PDF Document Navigation:** When viewing `.docx` or `.txt` files that do not support `#page=N` PDF anchors, the viewer gracefully falls back to displaying document metadata and a download action.

---

### Task 1: Frontend Scaffolding, Styling Tokens & Vite Proxy

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.app.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/index.css`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Test: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: None (initial setup)
- Produces: Runnable React app with Vite dev server proxy (`/api/v1` -> `http://localhost:8000`), Tailwind CSS classes, KaTeX styles, and Vitest test runner setup.

- [ ] **Step 1: Write the failing smoke test**

Create `frontend/src/App.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import App from './App';

describe('App Smoke Test', () => {
  it('renders application workspace shell', () => {
    render(<App />);
    expect(screen.getByRole('banner')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/App.test.tsx`
Expected: FAIL (file or vitest not found).

- [ ] **Step 3: Scaffold Vite React TypeScript project and configure tools**

1. Run Vite scaffolding:
   `npm create vite@latest frontend -- --template react-ts`
2. Install UI dependencies:
   `cd frontend && npm install lucide-react react-markdown remark-math rehype-katex remark-gfm katex clsx tailwind-merge`
3. Install Dev & Test dependencies:
   `cd frontend && npm install -D tailwindcss@^3.4.17 postcss autoprefixer vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event @types/katex`
4. Configure `frontend/vite.config.ts`:
   - Set dev server proxy: `server: { proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } } }`
   - Setup Vitest globals: `test: { globals: true, environment: 'jsdom', setupFiles: ['./src/setupTests.ts'] }`
5. Create `frontend/src/setupTests.ts` importing `@testing-library/jest-dom`.
6. Configure `frontend/tailwind.config.js` and `frontend/postcss.config.js` with dark theme palette:
   - Obsidian bg: `#0d1117`, surface: `#161b22`, border: `#30363d`, accent: `#238636` / `#58a6ff`.
7. Import `katex/dist/katex.min.css` in `frontend/src/index.css`.
8. Provide minimal `frontend/src/App.tsx` containing `<header role="banner">Document Intelligence</header>`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- --run src/App.test.tsx`
Expected: PASS (1 passed).

- [ ] **Step 5: Commit**

```bash
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add frontend/
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(frontend): scaffold Vite React TypeScript workspace with Tailwind and Vitest"
```

---

### Task 2: Data Types & API Client Service

**Files:**
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/api/client.ts`
- Test: `frontend/src/api/client.test.ts`

**Interfaces:**
- Consumes: FastAPI endpoints (`/api/v1/health`, `/api/v1/files`, `/api/v1/upload`, `/api/v1/files/{filename}`, `/api/v1/query`)
- Produces:
  - TypeScript types: `HealthResponse`, `FileInfo`, `FileListResponse`, `FileUploadResponse`, `Citation`, `EvidenceChunk`, `ReasoningStep`, `QAResponse`, `ChatMessageData`
  - Functions: `checkHealth()`, `getFiles()`, `uploadDocument(file: File)`, `deleteDocument(filename: string)`, `askQuestion(question: string, topK?: number)`, `getDocumentStreamUrl(filename: string, page?: number)`

- [ ] **Step 1: Write the failing API client tests**

Create `frontend/src/api/client.test.ts`:
```ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  checkHealth,
  getFiles,
  uploadDocument,
  deleteDocument,
  askQuestion,
  getDocumentStreamUrl,
} from './client';

describe('ApiClient Service', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('checkHealth returns backend status', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'healthy', vector_store_count: 42 }),
    } as Response);

    const res = await checkHealth();
    expect(res.status).toBe('healthy');
    expect(res.vector_store_count).toBe(42);
  });

  it('getDocumentStreamUrl encodes Vietnamese filenames and appends page hash', () => {
    const url = getDocumentStreamUrl('tài liệu máy bơm.pdf', 11);
    expect(url).toContain(encodeURIComponent('tài liệu máy bơm.pdf'));
    expect(url).toContain('#page=11');
  });

  it('askQuestion sends question and top_k to /api/v1/query', async () => {
    const mockQA = {
      answer: 'Reynolds Re = 228,571',
      citations: [{ filename: 'test.pdf', page: 8 }],
      evidence: [],
      reasoning_steps: [{ node: 'retrieve', status: 'completed' }],
    };
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => mockQA,
    } as Response);

    const res = await askQuestion('Tính Reynolds', 10);
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/v1/query',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: 'Tính Reynolds', top_k: 10 }),
      })
    );
    expect(res.answer).toBe('Reynolds Re = 228,571');
  });

  it('throws friendly error on network failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 503,
      statusText: 'Service Unavailable',
    } as Response);

    await expect(askQuestion('fail')).rejects.toThrow('Service Unavailable');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- --run src/api/client.test.ts`
Expected: FAIL (modules not found).

- [ ] **Step 3: Implement `types/index.ts` and `api/client.ts`**

Define all types in `frontend/src/types/index.ts` exactly mirroring FastAPI models.
Implement `frontend/src/api/client.ts`:
- Handle base URL `/api/v1`.
- In `getDocumentStreamUrl(filename, page)`: use `encodeURIComponent(filename)` and `#page=${page}`.
- In `uploadDocument(file)`: build `FormData`, attach `file`, POST to `/api/v1/upload`.
- In `deleteDocument(filename)`: DELETE to `/api/v1/files/${encodeURIComponent(filename)}`.
- In `askQuestion(question, topK = 8)`: POST to `/api/v1/query` with `{ question, top_k: topK }`. Throw formatted errors if response not `ok`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- --run src/api/client.test.ts`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add frontend/src/types frontend/src/api
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(frontend): implement TypeScript interfaces and typed API client service"
```

---

### Task 3: Layout Components (Header & Sidebar)

**Files:**
- Create: `frontend/src/components/layout/Header.tsx`
- Create: `frontend/src/components/layout/Sidebar.tsx`
- Test: `frontend/src/components/layout/Sidebar.test.tsx`
- Test: `frontend/src/components/layout/Header.test.tsx`

**Interfaces:**
- Consumes: `types/index.ts` (`FileInfo`, `HealthResponse`)
- Produces:
  - `Header`: props `{ isViewerOpen: boolean; onToggleViewer: () => void; isSidebarOpen: boolean; onToggleSidebar: () => void; health: HealthResponse | null; }`
  - `Sidebar`: props `{ isOpen: boolean; onClose: () => void; files: FileInfo[]; topK: number; onTopKChange: (val: number) => void; onNewChat: () => void; onFileUpload: (file: File) => Promise<void>; onDeleteFile: (filename: string) => Promise<void>; isUploading?: boolean; }`

- [ ] **Step 1: Write failing tests for Header and Sidebar**

Create `frontend/src/components/layout/Header.test.tsx`:
```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Header from './Header';

describe('Header Component', () => {
  it('renders title and triggers sidebar toggle', () => {
    const onToggleSidebar = vi.fn();
    render(
      <Header
        isViewerOpen={false}
        onToggleViewer={vi.fn()}
        isSidebarOpen={true}
        onToggleSidebar={onToggleSidebar}
        health={{ status: 'healthy', vector_store_count: 5 }}
      />
    );
    expect(screen.getByText(/Document Intelligence/i)).toBeInTheDocument();
    expect(screen.getByText(/5 chunks/i)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/toggle sidebar/i));
    expect(onToggleSidebar).toHaveBeenCalled();
  });
});
```

Create `frontend/src/components/layout/Sidebar.test.tsx`:
```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Sidebar from './Sidebar';

describe('Sidebar Component', () => {
  const files = [{ filename: 'tài liệu máy bơm.pdf', size: 1048576 }];

  it('renders file list and allows deleting file', () => {
    const onDeleteFile = vi.fn();
    render(
      <Sidebar
        isOpen={true}
        onClose={vi.fn()}
        files={files}
        topK={8}
        onTopKChange={vi.fn()}
        onNewChat={vi.fn()}
        onFileUpload={vi.fn()}
        onDeleteFile={onDeleteFile}
      />
    );
    expect(screen.getByText('tài liệu máy bơm.pdf')).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/delete tài liệu máy bơm.pdf/i));
    expect(onDeleteFile).toHaveBeenCalledWith('tài liệu máy bơm.pdf');
  });

  it('handles topK slider change', () => {
    const onTopKChange = vi.fn();
    render(
      <Sidebar
        isOpen={true}
        onClose={vi.fn()}
        files={files}
        topK={8}
        onTopKChange={onTopKChange}
        onNewChat={vi.fn()}
        onFileUpload={vi.fn()}
        onDeleteFile={vi.fn()}
      />
    );
    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '12' } });
    expect(onTopKChange).toHaveBeenCalledWith(12);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test -- --run src/components/layout/`
Expected: FAIL (components do not exist).

- [ ] **Step 3: Implement `Header.tsx` and `Sidebar.tsx`**

- `Header.tsx`:
  - Obsidian theme banner with branding icon (Sparkles or Bot), title "Document Intelligence", subtitle "TCVN & ISO Grounded".
  - Status pill: green dot for "Sẵn sàng" with chunk count, or yellow/red for connecting/error.
  - Buttons: Toggle Sidebar, Toggle Document Viewer.
- `Sidebar.tsx`:
  - "Cuộc trò chuyện mới" button with Plus icon.
  - Search Depth slider: label with current value (`k = {topK}`), range 1 to 20.
  - Indexed Documents section: scrollable list of files with file icon, truncated filename, formatted size (`1.0 MB`), and trash icon with aria-label.
  - File Dropzone: drag-and-drop or file input supporting `.pdf`, `.docx`, `.txt`, `.md`. Shows uploading spinner when `isUploading` is true.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm run test -- --run src/components/layout/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add frontend/src/components/layout/
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(frontend): implement Header and Sidebar layout components"
```

---

### Task 4: Chat Assistant Components (KaTeX, Reasoning & Citations)

**Files:**
- Create: `frontend/src/components/chat/CitationBadge.tsx`
- Create: `frontend/src/components/chat/ReasoningSteps.tsx`
- Create: `frontend/src/components/chat/EvidenceExpander.tsx`
- Create: `frontend/src/components/chat/EmptyHero.tsx`
- Create: `frontend/src/components/chat/ChatInput.tsx`
- Create: `frontend/src/components/chat/ChatMessage.tsx`
- Test: `frontend/src/components/chat/ChatMessage.test.tsx`
- Test: `frontend/src/components/chat/ChatInput.test.tsx`

**Interfaces:**
- Consumes: `types/index.ts` (`Citation`, `EvidenceChunk`, `ReasoningStep`, `ChatMessageData`)
- Produces:
  - `CitationBadge`: props `{ citation: Citation; onClick: (filename: string, page?: number) => void }`
  - `ReasoningSteps`: props `{ steps: ReasoningStep[] }`
  - `EvidenceExpander`: props `{ evidence: EvidenceChunk[] }`
  - `EmptyHero`: props `{ onSelectPrompt: (prompt: string) => void }`
  - `ChatInput`: props `{ onSendMessage: (msg: string) => void; isQuerying: boolean }`
  - `ChatMessage`: props `{ message: ChatMessageData; onCitationClick: (filename: string, page?: number) => void }`

- [ ] **Step 1: Write failing tests for ChatMessage and ChatInput**

Create `frontend/src/components/chat/ChatMessage.test.tsx`:
```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ChatMessage from './ChatMessage';
import { ChatMessageData } from '../../types';

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
});
```

Create `frontend/src/components/chat/ChatInput.test.tsx`:
```tsx
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

  it('disables input when isQuerying is true', () => {
    render(<ChatInput onSendMessage={vi.fn()} isQuerying={true} />);
    const textarea = screen.getByPlaceholderText(/Hệ thống đang xử lý/i);
    expect(textarea).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test -- --run src/components/chat/`
Expected: FAIL (modules not found).

- [ ] **Step 3: Implement Chat sub-components and ChatMessage**

- `CitationBadge.tsx`:
  - Clickable pill button with FileText icon, document name, page badge.
  - Hover effect with glowing border and tooltip.
- `ReasoningSteps.tsx`:
  - Collapsible card with ChevronDown/Right.
  - Displays LangGraph nodes (`retrieve`, `rerank`, `grade`, `generate`) with success/in-progress icons.
- `EvidenceExpander.tsx`:
  - Collapsible card displaying retrieved chunks with source filename, page, score, and text excerpt.
- `EmptyHero.tsx`:
  - 3 suggestion cards (Reynolds calculation, Centrifugal pump test, Volume flow rate).
  - Clicking any card triggers `onSelectPrompt(text)`.
- `ChatInput.tsx`:
  - Auto-growing textarea, submit button with Send icon or Spinner.
  - Enter sends, Shift+Enter adds newline.
- `ChatMessage.tsx`:
  - Markdown renderer configured with `remark-math`, `rehype-katex` (with `strict: false` to avoid KaTeX crashes), `remark-gfm`.
  - Integrates `ReasoningSteps`, `CitationBadge` container, and `EvidenceExpander`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd frontend && npm run test -- --run src/components/chat/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add frontend/src/components/chat/
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(frontend): implement KaTeX-enabled ChatMessage, Citations, Reasoning timeline and ChatInput"
```

---

### Task 5: Document / PDF Viewer Component with Page Sync

**Files:**
- Create: `frontend/src/components/viewer/DocumentViewer.tsx`
- Test: `frontend/src/components/viewer/DocumentViewer.test.tsx`

**Interfaces:**
- Consumes: `types/index.ts`
- Produces: `DocumentViewer`: props `{ activeDocument: { filename: string; page?: number } | null; onClose: () => void; onPageChange?: (page: number) => void; }`

- [ ] **Step 1: Write failing test for DocumentViewer**

Create `frontend/src/components/viewer/DocumentViewer.test.tsx`:
```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import DocumentViewer from './DocumentViewer';

describe('DocumentViewer Component', () => {
  it('renders empty state when no document is active', () => {
    render(<DocumentViewer activeDocument={null} onClose={vi.fn()} />);
    expect(screen.getByText(/Chọn hoặc bấm vào một trích dẫn/i)).toBeInTheDocument();
  });

  it('renders document iframe with encoded URL and page anchor', () => {
    render(
      <DocumentViewer
        activeDocument={{ filename: 'tài liệu máy bơm.pdf', page: 11 }}
        onClose={vi.fn()}
      />
    );
    expect(screen.getByText('tài liệu máy bơm.pdf')).toBeInTheDocument();
    const iframe = screen.getByTitle('Document Preview') as HTMLIFrameElement;
    expect(iframe.src).toContain(encodeURIComponent('tài liệu máy bơm.pdf'));
    expect(iframe.src).toContain('#page=11');
  });

  it('supports page navigation controls', () => {
    const onPageChange = vi.fn();
    render(
      <DocumentViewer
        activeDocument={{ filename: 'test.pdf', page: 5 }}
        onClose={vi.fn()}
        onPageChange={onPageChange}
      />
    );
    fireEvent.click(screen.getByLabelText(/next page/i));
    expect(onPageChange).toHaveBeenCalledWith(6);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- --run src/components/viewer/`
Expected: FAIL.

- [ ] **Step 3: Implement `DocumentViewer.tsx`**

- Top Toolbar:
  - Document icon, truncated filename, open in new tab button.
  - Page navigation: `[<] Page [input] [>]`.
  - Close button `[X]` triggering `onClose()`.
- Viewer Canvas:
  - `iframe` pointing to `/api/v1/files/${encodeURIComponent(filename)}#page=${currentPage}`.
  - Empty state with empty document illustration and helper text when `activeDocument` is null.
  - Fallback download button in case browser PDF rendering is disabled.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- --run src/components/viewer/`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add frontend/src/components/viewer/
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(frontend): implement DocumentViewer with page navigation and safe encoding"
```

---

### Task 6: Workspace Split-Pane Integration & One-Click Citation Wire-up

**Files:**
- Create: `frontend/src/components/chat/ChatContainer.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: All components from Tasks 2-5
- Produces: Integrated master application coordinating Split-Pane layout, active conversation, citation synchronization, and API integration.

- [ ] **Step 1: Write integration tests in App.test.tsx**

Update `frontend/src/App.test.tsx`:
```tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import App from './App';

describe('App Split-Screen Workspace Integration', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    global.fetch = vi.fn().mockImplementation((url: string) => {
      if (url.includes('/api/v1/health')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ status: 'healthy', vector_store_count: 10 }),
        });
      }
      if (url.includes('/api/v1/files')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ files: [{ filename: 'tài liệu máy bơm.pdf', size: 1048576 }] }),
        });
      }
      if (url.includes('/api/v1/query')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            answer: 'Reynolds Re = 228,571 theo công thức chuẩn.',
            citations: [{ filename: 'tài liệu máy bơm.pdf', page: 8 }],
            evidence: [],
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
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- --run src/App.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Implement ChatContainer and integrate in App.tsx**

1. Create `frontend/src/components/chat/ChatContainer.tsx`:
   - Auto-scroll to bottom on new assistant response using `useRef`.
   - Renders `EmptyHero` when messages list is empty.
   - Maps over messages list to render `ChatMessage`s.
2. Complete `frontend/src/App.tsx`:
   - Maintain state for `messages`, `isQuerying`, `activeDocument`, `isViewerOpen`, `isSidebarOpen`, `topK`, `files`, `health`.
   - On citation click: `setActiveDocument({ filename, page })` and `setIsViewerOpen(true)`.
   - Split-pane layout: Chat Assistant occupies full width if viewer closed, or 60% when open (40% right pane).
   - On error from `/api/v1/query`: append assistant error message with retry button.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm run test -- --run src/App.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add frontend/src/
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "feat(frontend): integrate split-screen workspace with citation synchronization"
```

---

### Task 7: Production Build, Regression Testing & Documentation

**Files:**
- Modify: `frontend/package.json`
- Modify: `README.md`
- Test: All Vitest frontend tests + All pytest backend tests

**Interfaces:**
- Consumes: Entire frontend and backend codebases
- Produces: Production build artifacts in `frontend/dist/`, updated `README.md` with React frontend quickstart, verified zero backend regressions.

- [ ] **Step 1: Run production build**

Run: `cd frontend && npm run build`
Expected: Build finishes cleanly (`dist/` generated with zero errors).

- [ ] **Step 2: Run entire frontend Vitest suite**

Run: `cd frontend && npm run test -- --run`
Expected: 100% tests pass.

- [ ] **Step 3: Run entire backend pytest suite to verify zero regressions**

Run: `.venv/bin/pytest tests/`
Expected: 112 passed, 0 failed.

- [ ] **Step 4: Update README.md with React Frontend running guide**

Document how to run both servers:
1. Backend: `.venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload`
2. Frontend: `cd frontend && npm run dev` (running at `http://localhost:5173`)
3. Note that Streamlit remains available at `http://localhost:8501`.

- [ ] **Step 5: Commit**

```bash
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git add frontend/package.json README.md
DEVELOPER_DIR=/Library/Developer/CommandLineTools GIT_CONFIG_GLOBAL=/dev/null git commit -m "docs: add React frontend setup guide and verify production build"
```

