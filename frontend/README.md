# Document Intelligence Assistant - React Frontend

Modern React Single-Page Application (SPA) for the Agentic RAG Document Intelligence workspace.

## Tech Stack
- **Framework & Tooling:** Vite + React 19 + TypeScript
- **Styling:** Tailwind CSS (Obsidian/Slate theme palette)
- **Math & Markdown:** KaTeX + `react-markdown` + `remark-math` + `rehype-katex` + `remark-gfm`
- **Icons:** `lucide-react`
- **Testing:** Vitest + `@testing-library/react` + `jsdom`

## Scripts
- `npm run dev`: Launch Vite dev server with proxy to FastAPI backend (`http://localhost:8000/api/v1`)
- `npm run build`: Typecheck and produce production bundle in `dist/`
- `npm run test`: Run Vitest unit & smoke tests
- `npm run lint`: Run Oxlint linter
