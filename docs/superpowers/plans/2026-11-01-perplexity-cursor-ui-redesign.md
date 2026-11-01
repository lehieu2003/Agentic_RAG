# Perplexity Pro & Cursor UI Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the React frontend into an elite, modern engineering workspace inspired by Perplexity Pro, Cursor, and Linear, eliminating generic "AI-generated prototype" aesthetics.

**Architecture:** Pure frontend modernization. Retains existing typed API client and REST endpoints. Elevates Tailwind CSS design tokens, introduces Google Fonts (Inter & JetBrains Mono), refactors chat messages into document-style layouts with Perplexity-like Source Cards, converts the bulky reasoning box into a sleek 1-line thought trace, and redesigns the sidebar into segmented tabs (Chats vs Documents).

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Lucide React, KaTeX, React Markdown, Vitest, Testing Library, Vite.

**Spec:** `docs/superpowers/specs/2026-11-01-perplexity-cursor-ui-redesign-spec.md`

## Global Constraints
- Preserve 100% existing REST API endpoints, types, and client contracts in `frontend/src/types/index.ts` and `frontend/src/api/client.ts`.
- Dark Mode first (Deep Zinc `#09090b` OLED base) with WCAG 2.2 AA contrast ratios (minimum 4.5:1 for body text, 3:1 for large headers and interactive icons).
- Preserve all existing user interactions: file upload, deletion, citation jump-to-page, session creation/switching/deletion, and LaTeX rendering.
- No external heavy animation libraries (Framer Motion etc.); rely on native CSS transitions and Tailwind utility classes for peak performance.
- All 86 existing frontend tests (and 111 backend tests) must pass with zero regressions.

## Review Focus
1. Citation Clickability: Clicking any source card or inline citation must continue to trigger `onCitationClick` and jump to `#page={page}` in Document Viewer.
2. Responsive Split-Screen: On small screens (<768px), sidebar and document viewer must toggle cleanly as overlays without breaking the layout.
3. Accessible Contrast: Subtle borders (`border-white/[0.08]`) and muted text (`text-zinc-400`) must remain legible against `#09090b`.
4. Mobile Touch Targets: Buttons in sidebar, tabs, and chat messages must maintain at least 36px touch targets.
5. Zero Production Build Warnings: Vite bundle chunks must remain efficiently split under 300 kB.

---

### Task 1: Design Tokens, Typography & Base CSS

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/tailwind.config.js`
- Modify: `frontend/src/index.css`
- Test: `frontend/src/App.test.tsx`

- [ ] **Step 1: Update `frontend/index.html` with Google Fonts**
  Add preconnect and stylesheet links for `Inter` (weights 300, 400, 500, 600, 700) and `JetBrains Mono` (weights 400, 500, 600) to the `<head>`. Update page title to `Document Intelligence — AI Technical Research Workspace`.

- [ ] **Step 2: Update `frontend/tailwind.config.js` design tokens**
  Update `theme.extend`:
  - `fontFamily`:
    - `sans`: `['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif']`
    - `mono`: `['JetBrains Mono', 'ui-monospace', 'monospace']`
  - `colors`:
    - Define palette `canvas: '#09090b'`, `surface: '#121215'`, `surface-elevated: '#18181b'`, `surface-subtle: '#222227'`.
    - Keep `obsidian` token aliases so existing component references don't instantly break during the migration.
    - Add `brand-sky: '#38bdf8'`, `brand-emerald: '#10b981'`, `brand-violet: '#a855f7'`.

- [ ] **Step 3: Update `frontend/src/index.css`**
  - Set `body` background to `#09090b` with `font-sans antialiased text-zinc-200 selection:bg-sky-500/30 selection:text-white`.
  - Maintain `:focus-visible`, reduced-motion, and ultra-thin custom scrollbar rules.
  - Add typography polish for KaTeX and prose elements.

- [ ] **Step 4: Verify build & tests**
  Run: `cd frontend && npm run test -- --run && npm run build`
  Expected: All 86 tests pass, build succeeds.

- [ ] **Step 5: Commit changes**
  Run: `git commit -am "feat(ui): upgrade design tokens, typography, and base styles with Inter & JetBrains Mono"`

---

### Task 2: Header & App Layout Modernization

**Files:**
- Modify: `frontend/src/components/layout/Header.tsx`
- Modify: `frontend/src/App.tsx`
- Test: `frontend/src/components/layout/Header.test.tsx`
- Test: `frontend/src/App.test.tsx`

- [ ] **Step 1: Refactor `Header.tsx`**
  - Height: `h-13` (52px), sticky top, `bg-zinc-950/80 backdrop-blur-md border-b border-white/[0.06]`.
  - Replace clunky badge with modern breadcrumb: `Document Intelligence` / `TCVN & ISO Grounded` in subtle monospace pill.
  - Refined status pill: Minimalist dark pill with a glowing emerald pulse dot (`h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(16,185,129,0.6)]`), clean chunk count.
  - Minimal icon buttons for sidebar and document viewer toggling with hover tooltips and sleek active state (`bg-white/[0.08] text-white`).

- [ ] **Step 2: Update `App.tsx` layout & error banner**
  - Modernize split-screen workspace container with subtle 1px divider `border-white/[0.06]`.
  - Floating error banner: Glassmorphism `bg-rose-950/90 border border-rose-500/30 backdrop-blur-md shadow-2xl rounded-xl`.

- [ ] **Step 3: Verify tests**
  Run: `cd frontend && npm run test -- src/components/layout/Header.test.tsx src/App.test.tsx`
  Expected: Header and App tests pass.

- [ ] **Step 4: Commit changes**
  Run: `git commit -am "feat(ui): modernize header and app split-screen layout with glassmorphic styling"`

---

### Task 3: Sidebar Segmented Tabs & Modern Dropzone

**Files:**
- Modify: `frontend/src/components/layout/Sidebar.tsx`
- Test: `frontend/src/components/layout/Sidebar.test.tsx`

- [ ] **Step 1: Implement Segmented Control in `Sidebar.tsx`**
  - Add tab state: `activeTab: 'chats' | 'documents'` (default `'chats'`).
  - Render sleek segmented pill buttons at the top of the sidebar:
    - Tab 1: `Cuộc trò chuyện` (with MessageSquare icon)
    - Tab 2: `Kho tài liệu` (with Files icon)
  - Seamlessly switch content between chat session list and document ingestion/library.

- [ ] **Step 2: Modernize Chats Tab**
  - Top "Cuộc trò chuyện mới" (New Chat) button: Sleek full-width button with Plus icon and subtle border glow.
  - Session items: Clean cards with hover actions, active session highlighted with `bg-white/[0.06] text-white border-l-2 border-sky-400`, smooth delete confirmation with trash icon.

- [ ] **Step 3: Modernize Documents Tab**
  - Drag-and-drop zone: Animated border on dragover (`border-dashed border-sky-400/80 bg-sky-500/5`), clear file type pills (PDF, DOCX, TXT, PNG).
  - Search depth slider: Styled slider track with gradient fill and numeric pill `k = {topK}`.
  - Document items: Clean card with file type icon, filename, page count or size, and delete button with confirmation dialog.

- [ ] **Step 4: Verify tests**
  Run: `cd frontend && npm run test -- src/components/layout/Sidebar.test.tsx`
  Update any test selectors if needed to ensure all 15 tests pass.

- [ ] **Step 5: Commit changes**
  Run: `git commit -am "feat(ui): redesign sidebar with segmented tabs and modern drag-and-drop zone"`

---

### Task 4: Empty State & Floating Chat Input

**Files:**
- Modify: `frontend/src/components/chat/EmptyHero.tsx`
- Modify: `frontend/src/components/chat/ChatInput.tsx`
- Test: `frontend/src/components/chat/EmptyHero.test.tsx`
- Test: `frontend/src/components/chat/ChatInput.test.tsx`

- [ ] **Step 1: Refactor `EmptyHero.tsx`**
  - Hero header: Clean glowing icon (`Sparkles`), sharp title `Trợ lý Trí tuệ Tài liệu Kỹ thuật`, concise subtitle.
  - Suggestion cards: Grid of 3 Raycast/Perplexity-style cards with subtle border `border-white/[0.06] hover:border-sky-500/40 hover:bg-zinc-900/80 transition-all duration-200`, icon badge, category tag, and subtle arrow.

- [ ] **Step 2: Refactor `ChatInput.tsx`**
  - Floating container: Centered max-w-4xl, `bg-zinc-900/85 backdrop-blur-xl border border-white/[0.1] rounded-2xl shadow-[0_8px_32px_rgba(0,0,0,0.4)]`.
  - Textarea: Clean font, placeholder with subtle color, auto-height resizing.
  - Send button: Sleek circular/rounded-xl button `bg-sky-500 hover:bg-sky-400 text-zinc-950 font-semibold transition-all duration-200 hover:shadow-[0_0_16px_rgba(56,189,248,0.4)]`.
  - Footer hint: Micro-pills for `Enter ↵` and `Shift + Enter`.

- [ ] **Step 3: Verify tests**
  Run: `cd frontend && npm run test -- src/components/chat/EmptyHero.test.tsx src/components/chat/ChatInput.test.tsx`
  Expected: All tests pass.

- [ ] **Step 4: Commit changes**
  Run: `git commit -am "feat(ui): redesign empty state hero and floating glassmorphic chat input"`

---

### Task 5: Chat Message, Collapsible Reasoning Trace & Source Cards

**Files:**
- Modify: `frontend/src/components/chat/ReasoningSteps.tsx`
- Modify: `frontend/src/components/chat/CitationBadge.tsx`
- Modify: `frontend/src/components/chat/EvidenceExpander.tsx`
- Modify: `frontend/src/components/chat/ChatMessage.tsx`
- Test: `frontend/src/components/chat/ReasoningSteps.test.tsx`
- Test: `frontend/src/components/chat/CitationBadge.test.tsx`
- Test: `frontend/src/components/chat/EvidenceExpander.test.tsx`
- Test: `frontend/src/components/chat/ChatMessage.test.tsx`

- [ ] **Step 1: Redesign `ReasoningSteps.tsx` (DeepSeek / Perplexity Thought Trace)**
  - Collapsed state: Minimalist 1-line bar `✦ Đã suy luận qua N bước` with subtle micro-tags for completed steps.
  - Expanded state: Elegant vertical timeline with thin connecting line, pulsing active node, and clean step descriptions.

- [ ] **Step 2: Redesign `CitationBadge.tsx`**
  - Sleek interactive micro-pill: `[P.12 - Tên tệp]` with subtle border `border-sky-500/30 bg-sky-500/10 text-sky-400 hover:bg-sky-500/20 hover:border-sky-400 transition-colors`.

- [ ] **Step 3: Redesign `EvidenceExpander.tsx` (Perplexity-style Source Cards Grid)**
  - Collapsed bar: `✦ N nguồn tham khảo từ tài liệu`.
  - Expanded state: Grid of Source Cards with document icon, filename in bold, page pill, similarity percentage badge with emerald ring, and snippet preview.

- [ ] **Step 4: Redesign `ChatMessage.tsx`**
  - User message: Floating right-aligned capsule with sleek border `bg-zinc-800/90 border border-white/[0.08] text-zinc-100`.
  - Assistant message: Document-style reading layout, minimal sparkle avatar, code blocks with sleek header and copy button, clean KaTeX formulas, and elegant standalone query badge `✦ Đã hiểu ngữ cảnh: "..."`.

- [ ] **Step 5: Verify all message tests**
  Run: `cd frontend && npm run test -- src/components/chat/`
  Expected: All component tests pass.

- [ ] **Step 6: Commit changes**
  Run: `git commit -am "feat(ui): implement perplexity-style source cards, thought trace, and document chat layout"`

---

### Task 6: Document Viewer Glass Toolbar & Full Regression

**Files:**
- Modify: `frontend/src/components/viewer/DocumentViewer.tsx`
- Test: `frontend/src/components/viewer/DocumentViewer.test.tsx`
- Test: `frontend/src/App.test.tsx`

- [ ] **Step 1: Refactor `DocumentViewer.tsx`**
  - Top toolbar: `bg-zinc-950/80 backdrop-blur-md border-b border-white/[0.06]`.
  - Page navigation: Sleek controls with page counter `Trang X / Y`, zoom percentage, open in new tab button, and close button.
  - Empty and loading states with refined animations.

- [ ] **Step 2: Run complete frontend test suite**
  Run: `cd frontend && npm run test -- --run`
  Expected: 86/86 passed.

- [ ] **Step 3: Run Vite production build**
  Run: `cd frontend && npm run build`
  Expected: Production build compiles in < 500ms with zero errors.

- [ ] **Step 4: Run backend test suite**
  Run: `.venv/bin/pytest tests/`
  Expected: 111/111 passed.

- [ ] **Step 5: Commit changes & push**
  Run: `git commit -am "feat(ui): complete Perplexity Pro & Cursor redesign for Document Q&A Assistant"`
