# Specification: Perplexity Pro & Cursor UI Redesign for Document Q&A Assistant

## 1. Executive Summary & Objective

Transform the current React SPA from a generic, prototype-style "ChatGPT wrapper" into an elite, production-grade **Technical Research & Engineering Workspace** inspired by **Perplexity Pro**, **Cursor**, and **Linear**.

### Key Problems with Current UI:
1. **Harsh Boxy Layout:** Solid `#30363d` 1px borders dividing every element into rigid rectangles on a murky dark gray background (`#0d1117`).
2. **"Debug-Dump" AI Clichés:** Bulky purple "Reasoning Steps" accordion and green "Evidence" tables displayed prominently between chat bubbles, looking like internal dev logs rather than an elegant user experience.
3. **Typography Disconnect:** Default system font stack (`-apple-system`) without technical precision fonts like **Inter** and **JetBrains Mono**.
4. **Monolithic Sidebar:** All features (uploads, document list, settings, session history) stacked in one vertical scrollable pane without logical grouping.

---

## 2. Design System Tokens & Foundations (ui-ux-pro-max)

### 2.1. Color Palette (Deep Zinc & OLED Dark)
| Token Name | Value | Purpose |
| :--- | :--- | :--- |
| `--bg-canvas` | `#09090b` (Zinc-950) | Base application background (deep black-zinc, OLED-efficient) |
| `--bg-surface` | `rgba(18, 18, 21, 0.75)` | Sidebar, Header, Document Viewer panels with backdrop-blur |
| `--bg-elevated` | `rgba(24, 24, 27, 0.85)` | Cards, User message bubbles, hover states |
| `--border-subtle` | `rgba(255, 255, 255, 0.08)` | Crisp, ultra-thin boundary dividers |
| `--border-focus` | `#38bdf8` (Sky-400) | Keyboard navigation and focus ring |
| `--text-primary` | `#f4f4f5` (Zinc-100) | Main reading text, headings |
| `--text-muted` | `#a1a1aa` (Zinc-400) | Secondary metadata, captions, timestamps |
| `--accent-sky` | `#38bdf8` (Sky-400) | Citation badges, active tabs, interactive links |
| `--accent-emerald`| `#10b981` (Emerald-500) | Health indicators, high similarity scores |
| `--accent-violet` | `#a855f7` (Purple-500) | AI reasoning / Agentic thinking steps |

### 2.2. Typography System
- **Primary Sans:** `Inter`, `-apple-system`, `BlinkMacSystemFont`, `sans-serif`
  - Body: 14px, `leading-relaxed`, `tracking-[-0.01em]`
  - Headings: Bold/Semibold, `tracking-[-0.025em]`
- **Technical Mono:** `JetBrains Mono`, `ui-monospace`, `monospace`
  - Code blocks, formula annotations, page badges (`P. 3`), similarity scores (`94.2%`).

### 2.3. Micro-Interactions & Ambient Lighting
- Subtle gradient hover glows (`hover:shadow-[0_0_20px_rgba(56,189,248,0.15)]`).
- Glassmorphism: `backdrop-blur-md` on Header, Sidebar, and floating Chat Input.
- Full respect for `@media (prefers-reduced-motion: reduce)`.

---

## 3. Component Architecture & UI Transformation

### 3.1. Header & Navigation (`src/components/layout/Header.tsx`)
- Sleek 52px height bar with `backdrop-blur-md` and 1px bottom border `border-white/[0.06]`.
- Minimalist branding: Lucide `Sparkles` icon with soft gradient glow.
- Status Indicator: Minimalist pill with a glowing emerald pulse dot (`● Sẵn sàng • 1,240 chunks`).
- Clean toggle buttons for Sidebar and Document Viewer.

### 3.2. Segmented Sidebar (`src/components/layout/Sidebar.tsx`)
- **Segmented Control Tabs at Top:**
  - Tab 1: **Cuộc trò chuyện (Chats)** — Recent conversations list with active thread highlight, delete confirmation, and quick "New Chat" button.
  - Tab 2: **Tài liệu (Documents)** — File upload dropzone, storage usage, search depth slider (`top_k`), and file management list.
- **Modern Dropzone:** Animated dashed border on dragover (`border-sky-400 bg-sky-500/10`), progress states, and clear multi-format badges.

### 3.3. Chat Area & Message Flow (`src/components/chat/`)
1. **Empty State (`EmptyHero.tsx`):**
   - Clean prompt suggestion cards with icon, category badge, and arrow indicator.
   - High visual contrast without oversized clunky graphic icons.
2. **User Message:**
   - Right-aligned floating capsule (`bg-zinc-800/90 border border-white/[0.08]`), clean rounded corners (`rounded-2xl rounded-tr-sm`).
3. **Assistant Message (`ChatMessage.tsx`):**
   - Document-style presentation without heavy chat bubbles.
   - **Reasoning Trace (`ReasoningSteps.tsx`):**
     - Single-line sleek collapsible bar: `✦ Đã suy luận qua 4 bước (0.8s)`.
     - Expanding reveals a vertical timeline with connecting lines and status icons.
   - **Source Cards Grid (`EvidenceExpander.tsx` & `CitationBadge.tsx`):**
     - Replaces heavy table with horizontal or multi-column **Source Cards** (file name, page tag `P.12`, cosine similarity percentage, snippet preview).
     - Clicking any card or inline citation badge opens Document Viewer and jumps to `#page={page}`.
   - **Markdown & Math Presentation:**
     - High-contrast KaTeX formula rendering.
     - Clean GFM tables with subtle zebra-striping.
     - Code blocks with syntax styling and a 1-click "Sao chép" (Copy) button.
4. **Chat Input (`ChatInput.tsx`):**
   - Centered floating island with glassmorphism `bg-zinc-900/80 backdrop-blur-lg border border-white/[0.1] shadow-2xl`.
   - Auto-resizing textarea with clear keyboard shortcut indicators (`Enter ↵`, `Shift + Enter`).

### 3.4. Document Viewer (`src/components/viewer/DocumentViewer.tsx`)
- Top glassmorphic toolbar with page navigation (`Trang X / Y`), zoom in/out, download/external tab link, and close panel button.
- Clean empty and loading states.

---

## 4. Verification & Non-Breaking Requirements
- 100% backward compatibility: Zero backend API changes.
- 100% passing test coverage: All 86 Vitest tests and 111 Pytest tests must pass without regressions.
- Vite production build must succeed with zero errors and clean chunk splitting.
