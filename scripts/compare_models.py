"""Compare embedding/reranker configurations on the real upload corpus.

Each configuration gets its own freshly built index (temporary local Qdrant +
BM25) from the same extracted pages, so the only difference is the models.
Nothing is read from or written to the production Qdrant collections.

Metrics:
  A. Label-based (synthetic QA, page labels): Recall@1/3/5 and MRR@5 for the
     dense, hybrid (RRF) and hybrid+rerank stages.
  B. Label-free (LLM judge): the final top-5 of every config is pooled, shuffled
     and graded blind (0/1/2) -> graded precision@5, nDCG@5, win/tie/loss.

Usage:
    python scripts/compare_models.py
    python scripts/compare_models.py --no-judge --limit 20
"""

import argparse
import gc
import json
import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List

os.environ.setdefault("HF_HUB_OFFLINE", "1")
_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from src.config import settings
from src.eval.metrics import calculate_mrr_at_k, calculate_recall_at_k
from src.eval.synthetic import (
    graded_ndcg,
    judge_passages,
    load_corpus_pages,
    make_gemini_llm,
    shuffled_pool,
)
from src.ingestion.chunker import chunk_document
from src.ingestion.tokenization import get_chunk_token_limit
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.hybrid import HybridRetriever
from src.retrieval.local import LocalRetriever
from src.retrieval.reranker import CrossEncoderReranker
from src.vector_store.embedding import EmbeddingModel
from src.vector_store.qdrant_store import QdrantVectorStore

DEFAULT_CONFIGS = [
    {"name": "old", "embedding": "sentence-transformers/all-MiniLM-L6-v2", "reranker": "BAAI/bge-reranker-base"},
    {"name": "new", "embedding": "intfloat/multilingual-e5-large-instruct", "reranker": "BAAI/bge-reranker-v2-m3"},
]
STAGES = ("dense", "hybrid", "rerank")
K_VALUES = (1, 3, 5)
CANDIDATES = 20
FINAL_K = 5


def _serialize(results) -> List[Dict[str, Any]]:
    return [
        {"doc_name": r.chunk.doc_name, "page": r.chunk.page_number, "score": round(float(r.score), 4), "text": r.chunk.text}
        for r in results
    ]


def run_config(cfg: Dict[str, str], pages: List[Dict[str, Any]], questions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build an isolated index for one config and run every question through it."""
    print(f"\n=== {cfg['name']}: {cfg['embedding']} + {cfg['reranker']} ===")
    embedder = EmbeddingModel(
        cfg["embedding"],
        device=settings.embedding_device or None,
        max_seq_length=settings.embedding_max_seq_length,
        batch_size=settings.embedding_batch_size,
    )
    token_limit = get_chunk_token_limit(embedder.max_seq_length, settings.chunk_size_tokens)
    chunks = chunk_document(
        [dict(p) for p in pages],
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        tokenizer=embedder.tokenizer,
        max_tokens=token_limit,
        overlap_tokens=settings.chunk_overlap_tokens,
    )
    reranker = CrossEncoderReranker(model_name=cfg["reranker"], device=settings.embedding_device or None)

    rows: List[Dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="rag_compare_") as tmp:
        store = QdrantVectorStore(
            storage_path=str(Path(tmp) / "qdrant"),
            collection_name=f"compare_{cfg['name']}",
            vector_size=embedder.dimension,
            url=None,
            api_key=None,
        )
        try:
            dense = LocalRetriever(embedder, store)
            hybrid = HybridRetriever(dense_retriever=dense, sparse_retriever=BM25Retriever(), rrf_k=settings.hybrid_rrf_k)
            t0 = time.perf_counter()
            hybrid.index_chunks(chunks)
            index_s = time.perf_counter() - t0
            print(f"Indexed {len(chunks)} chunks (token limit {token_limit}) in {index_s:.1f}s")

            for i, q in enumerate(questions, 1):
                t0 = time.perf_counter()
                dense_res = dense.search(q["question"], top_k=CANDIDATES)
                t1 = time.perf_counter()
                hybrid_res = hybrid.search(q["question"], top_k=CANDIDATES)
                t2 = time.perf_counter()
                rerank_res = reranker.rerank(q["question"], hybrid_res, top_k=FINAL_K)
                t3 = time.perf_counter()

                row: Dict[str, Any] = {
                    "id": q["id"],
                    "latency_ms": {"dense": (t1 - t0) * 1000, "hybrid": (t2 - t1) * 1000, "rerank": (t3 - t2) * 1000},
                    "top5": _serialize(rerank_res),
                }
                for stage, res in zip(STAGES, (dense_res, hybrid_res, rerank_res)):
                    for k in K_VALUES:
                        row[f"{stage}_recall@{k}"] = calculate_recall_at_k(res, q["expected_doc"], q["expected_pages"], k)
                    row[f"{stage}_mrr@5"] = calculate_mrr_at_k(res, q["expected_doc"], q["expected_pages"], 5)
                rows.append(row)
                if i % 20 == 0:
                    print(f"  {i}/{len(questions)} questions")
        finally:
            store.close()

    del embedder, reranker
    gc.collect()
    return {"config": cfg, "num_chunks": len(chunks), "index_seconds": index_s, "rows": rows}


def summarize_labels(run: Dict[str, Any]) -> Dict[str, float]:
    rows = run["rows"]
    out: Dict[str, float] = {}
    for stage in STAGES:
        for k in K_VALUES:
            out[f"{stage}_recall@{k}"] = mean(r[f"{stage}_recall@{k}"] for r in rows)
        out[f"{stage}_mrr@5"] = mean(r[f"{stage}_mrr@5"] for r in rows)
    out["query_latency_ms"] = mean(sum(r["latency_ms"].values()) for r in rows)
    return out


def run_judge(questions, runs, llm, workers: int) -> Dict[str, Any]:
    """Pool final top-5 passages per question, grade blind, and score each config."""
    names = [run["config"]["name"] for run in runs]
    by_id = {name: {r["id"]: r for r in run["rows"]} for name, run in zip(names, runs)}

    def _grade(item):
        idx, q = item
        texts = {name: [p["text"] for p in by_id[name][q["id"]]["top5"]] for name in names}
        pool = shuffled_pool(texts, seed=idx)
        grades = judge_passages(q["question"], pool, llm)
        grade_of = {text: g for text, g in zip(pool, grades)}
        return q["id"], {name: [grade_of.get(t.strip()) for t in texts[name]] for name in names}, grades

    with ThreadPoolExecutor(max_workers=workers) as ex:
        graded = list(ex.map(_grade, enumerate(questions)))

    per_question = []
    summary = {name: {"precision@5": [], "ndcg@5": [], "hit@5": []} for name in names}
    wins = {name: 0 for name in names}
    ties = 0
    for qid, config_grades, pool_grades in graded:
        if any(g is None for g in pool_grades):
            continue  # judge returned an incomplete answer; drop the question
        totals = {}
        for name in names:
            gs = config_grades[name]
            summary[name]["precision@5"].append(sum(g for g in gs) / (2 * FINAL_K))
            summary[name]["ndcg@5"].append(graded_ndcg(gs, pool_grades, FINAL_K))
            summary[name]["hit@5"].append(1.0 if any(g == 2 for g in gs) else 0.0)
            totals[name] = graded_ndcg(gs, pool_grades, FINAL_K)
        best = max(totals.values())
        leaders = [n for n, v in totals.items() if abs(v - best) < 1e-9]
        if len(leaders) > 1:
            ties += 1
        else:
            wins[leaders[0]] += 1
        per_question.append({"id": qid, "grades": config_grades})

    judged = len(per_question)
    return {
        "judged_questions": judged,
        "dropped_questions": len(graded) - judged,
        "metrics": {n: {m: (mean(v) if v else 0.0) for m, v in d.items()} for n, d in summary.items()},
        "wins": wins,
        "ties": ties,
        "per_question": per_question,
    }


def render_markdown(meta, runs, label_summary, judge) -> str:
    names = [r["config"]["name"] for r in runs]
    lines = [
        "# So sánh cấu hình retrieval trên tài liệu thật",
        "",
        f"- Thời điểm: {meta['timestamp']}",
        f"- Bộ câu hỏi: `{meta['questions_file']}` ({meta['num_questions']} câu, nhãn = trang sinh ra câu hỏi)",
        f"- Corpus: {meta['num_pages']} trang từ `{meta['upload_dir']}`",
        "",
        "| Config | Embedding | Reranker | Chunks | Index (s) | Latency/query (ms) |",
        "|---|---|---|---:|---:|---:|",
    ]
    for run in runs:
        c = run["config"]
        lines.append(
            f"| {c['name']} | `{c['embedding']}` | `{c['reranker']}` | {run['num_chunks']} | "
            f"{run['index_seconds']:.1f} | {label_summary[c['name']]['query_latency_ms']:.0f} |"
        )
    lines += ["", "## A. Theo nhãn trang (synthetic QA)", "", "| Metric | " + " | ".join(names) + " |", "|---|" + "---:|" * len(names)]
    for stage in STAGES:
        for metric in [f"recall@{k}" for k in K_VALUES] + ["mrr@5"]:
            key = f"{stage}_{metric}"
            lines.append(f"| {stage} {metric} | " + " | ".join(f"{label_summary[n][key]:.3f}" for n in names) + " |")
    if judge:
        lines += [
            "",
            f"## B. LLM judge (top-5 sau rerank, chấm mù 0/1/2) — {judge['judged_questions']} câu"
            f" (bỏ {judge['dropped_questions']} câu do judge trả thiếu)",
            "",
            "| Metric | " + " | ".join(names) + " |",
            "|---|" + "---:|" * len(names),
        ]
        for metric in ("precision@5", "ndcg@5", "hit@5"):
            lines.append(f"| {metric} | " + " | ".join(f"{judge['metrics'][n][metric]:.3f}" for n in names) + " |")
        lines.append("| thắng (nDCG@5) | " + " | ".join(str(judge["wins"][n]) for n in names) + " |")
        lines.append(f"| hoà | {judge['ties']} |" + " |" * (len(names) - 1))
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--questions", default="data/eval/synthetic_qa.json")
    parser.add_argument("--upload-dir", default=settings.upload_dir)
    parser.add_argument("--pages-cache", default="data/eval/.cache/pages.json")
    parser.add_argument("--configs", default=None, help="JSON list of {name, embedding, reranker}.")
    parser.add_argument("--limit", type=int, default=0, help="Use only the first N questions.")
    parser.add_argument("--no-judge", action="store_true", help="Skip method B (no LLM calls).")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--rpm", type=float, default=14, help="Max judge requests per minute.")
    parser.add_argument("--out-dir", default="data/eval/reports")
    args = parser.parse_args()

    questions = json.loads(Path(args.questions).read_text(encoding="utf-8"))
    questions = [q for q in questions if not q.get("should_abstain")]
    if args.limit:
        questions = questions[: args.limit]
    configs = json.loads(args.configs) if args.configs else DEFAULT_CONFIGS
    pages = load_corpus_pages(args.upload_dir, args.pages_cache)
    print(f"{len(questions)} questions | {len(pages)} pages | configs: {[c['name'] for c in configs]}")

    runs = [run_config(cfg, pages, questions) for cfg in configs]
    label_summary = {run["config"]["name"]: summarize_labels(run) for run in runs}

    judge = None
    if not args.no_judge:
        if not settings.gemini_api_key:
            raise SystemExit("GEMINI_API_KEY is empty; use --no-judge.")
        print("\nRunning LLM judge ...")
        judge = run_judge(questions, runs, make_gemini_llm(settings.gemini_api_key, settings.gemini_model, rpm=args.rpm), args.workers)

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    meta = {
        "timestamp": stamp,
        "questions_file": args.questions,
        "num_questions": len(questions),
        "num_pages": len(pages),
        "upload_dir": args.upload_dir,
        "judge_model": None if judge is None else settings.gemini_model,
    }
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    markdown = render_markdown(meta, runs, label_summary, judge)
    (out_dir / f"compare-{stamp}.md").write_text(markdown, encoding="utf-8")
    (out_dir / f"compare-{stamp}.json").write_text(
        json.dumps({"meta": meta, "labels": label_summary, "judge": judge, "runs": runs}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print("\n" + markdown)
    print(f"Reports: {out_dir}/compare-{stamp}.md (+ .json)")


if __name__ == "__main__":
    main()
