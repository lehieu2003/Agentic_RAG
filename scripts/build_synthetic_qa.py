"""Method A: generate a synthetic QA set (page-labelled) from the real uploads.

One question is generated per content page; the source page is the label.
Read-only: it only reads data/uploads and calls the LLM.

Usage:
    python scripts/build_synthetic_qa.py
    python scripts/build_synthetic_qa.py --max-pages 40 --output data/eval/synthetic_qa.json
"""

import argparse
import json
import os
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

os.environ.setdefault("HF_HUB_OFFLINE", "1")
_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from src.config import settings
from src.eval.synthetic import generate_question_for_page, load_corpus_pages, make_gemini_llm


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--upload-dir", default=settings.upload_dir)
    parser.add_argument("--pages-cache", default="data/eval/.cache/pages.json")
    parser.add_argument("--output", default="data/eval/synthetic_qa.json")
    parser.add_argument("--min-chars", type=int, default=300, help="Skip pages with less text.")
    parser.add_argument("--max-pages", type=int, default=0, help="Sample at most N pages (0 = all).")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--rpm", type=float, default=14, help="Max LLM requests per minute (free tier: 15).")
    parser.add_argument("--resume", action="store_true", help="Keep existing output; only fill missing pages.")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    if not settings.gemini_api_key:
        raise SystemExit("GEMINI_API_KEY is empty.")
    llm = make_gemini_llm(settings.gemini_api_key, settings.gemini_model, rpm=args.rpm)

    pages = load_corpus_pages(args.upload_dir, args.pages_cache)
    candidates = [p for p in pages if len(p["text"].strip()) >= args.min_chars]
    if args.max_pages and len(candidates) > args.max_pages:
        candidates = random.Random(args.seed).sample(candidates, args.max_pages)

    existing = []
    if args.resume and Path(args.output).exists():
        existing = json.loads(Path(args.output).read_text(encoding="utf-8"))
        done = {(q["expected_doc"], q["expected_pages"][0]) for q in existing}
        candidates = [p for p in candidates if (p["doc_name"], p["page_number"]) not in done]
    print(f"Pages extracted: {len(pages)} | to generate: {len(candidates)} | kept: {len(existing)}")

    def _work(page):
        try:
            return generate_question_for_page(page, llm)
        except Exception as exc:
            print(f"  ! {page['doc_name']} p{page['page_number']}: {exc}")
            return None

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(_work, candidates))

    merged = [{k: v for k, v in q.items() if k != "id"} for q in existing]
    merged += [r for r in results if r]
    merged.sort(key=lambda q: (q["expected_doc"], q["expected_pages"][0]))
    items = [{"id": f"s{idx + 1}", **item} for idx, item in enumerate(merged)]

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    new_count = sum(1 for r in results if r)
    print(f"New: {new_count} | skipped/failed: {len(candidates) - new_count} | total: {len(items)} -> {args.output}")


if __name__ == "__main__":
    main()
