"""Benchmark runner for retrieval quality, citation grounding, and abstention."""

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.eval.metrics import (
    calculate_citation_precision,
    calculate_mrr_at_k,
    calculate_ndcg_at_k,
    calculate_recall_at_k,
    calculate_token_f1,
    evaluate_abstention,
)
from src.models import QAResponse, RetrievalResult
from src.rag.generator import RAGGenerator
from src.retrieval.base import BaseRetriever

AnswerFn = Callable[[str], QAResponse]


def _average(values: List[float], default: Optional[float] = None) -> Optional[float]:
    """Return the rounded mean of values, or default when the list is empty."""
    if not values:
        return default
    return round(sum(values) / len(values), 4)


def _p95(values: List[float]) -> Optional[float]:
    """Return a simple nearest-rank p95 for the given values."""
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))
    return round(ordered[index], 2)


def _aggregate_rows(rows: List[Dict[str, Any]], k_values: List[int]) -> Dict[str, Any]:
    """Aggregate retrieval and answer metrics over a set of per-query rows."""
    metrics: Dict[str, Any] = {"num_queries": len(rows)}

    for k in k_values:
        metrics[f"recall@{k}"] = _average([row[f"recall@{k}"] for row in rows], default=0.0)
        metrics[f"mrr@{k}"] = _average([row[f"mrr@{k}"] for row in rows], default=0.0)
        metrics[f"ndcg@{k}"] = _average([row[f"ndcg@{k}"] for row in rows], default=0.0)

    answered_rows = [row for row in rows if not row.get("abstained", False)]
    metrics["citation_precision"] = _average(
        [row["citation_precision"] for row in answered_rows if "citation_precision" in row]
    )
    metrics["answer_f1"] = _average(
        [row["answer_f1"] for row in rows if "answer_f1" in row]
    )
    metrics["in_scope_abstention_rate"] = _average(
        [
            1.0 if row.get("abstained") else 0.0
            for row in rows
            if "abstained" in row and row.get("scope") == "in_scope"
        ]
    )
    metrics["mean_latency_ms"] = _average(
        [row["latency_ms"] for row in rows if "latency_ms" in row]
    )
    return metrics


def run_benchmark(
    retriever: BaseRetriever,
    ground_truth_file: str,
    k_values: Optional[List[int]] = None,
    rag_generator: Optional[RAGGenerator] = None,
    answer_fn: Optional[AnswerFn] = None,
    output_json: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a quantitative benchmark on a ground truth dataset.

    Args:
        retriever: Concrete BaseRetriever instance to evaluate.
        ground_truth_file: Path to ground truth JSON file.
        k_values: List of K values for Recall@K/MRR/nDCG (defaults to [1, 3, 5, 10]).
        rag_generator: Optional legacy RAGGenerator used for out-of-scope abstention.
        answer_fn: Optional end-to-end answer function (for example ``AgenticRAG.answer``).
            When provided, citation precision, answer F1 and per-bucket answer metrics
            are measured in addition to retrieval metrics.
        output_json: Optional path to write the full summary and per-query report as JSON.

    Returns:
        Summary metrics dictionary. Includes ``per_query`` and ``bucket_metrics`` for
        detailed inspection and regression tracking.
    """
    if k_values is None:
        k_values = [1, 3, 5, 10]

    gt_path = Path(ground_truth_file)
    if not gt_path.exists():
        raise FileNotFoundError(f"Ground truth file not found: {ground_truth_file}")

    with open(gt_path, "r", encoding="utf-8") as f:
        dataset: List[Dict[str, Any]] = json.load(f)

    in_scope_items = [item for item in dataset if not item.get("should_abstain", False)]
    out_of_scope_items = [item for item in dataset if item.get("should_abstain", False)]

    max_k = max(k_values)
    per_query_details: List[Dict[str, Any]] = []
    answer_mode = answer_fn is not None

    def _answer(query: str, retrieved: List[RetrievalResult]) -> Optional[QAResponse]:
        if answer_fn is not None:
            return answer_fn(query)
        if rag_generator is not None:
            return rag_generator.generate_answer(query, retrieved)
        return None

    # ------------------------------------------------------------------
    # In-scope queries: retrieval + optional end-to-end answer quality
    # ------------------------------------------------------------------
    for item in in_scope_items:
        query = item["question"]
        expected_doc = item.get("expected_doc")
        expected_pages = item.get("expected_pages") or []

        retrieval_start = time.perf_counter()
        retrieved: List[RetrievalResult] = retriever.search(query, top_k=max_k)
        retrieval_latency_ms = (time.perf_counter() - retrieval_start) * 1000

        row: Dict[str, Any] = {
            "id": item.get("id"),
            "bucket": item.get("bucket", "default"),
            "scope": "in_scope",
            "question": query,
            "expected": f"{expected_doc} p.{expected_pages}",
            "retrieved_top1": (
                f"{retrieved[0].chunk.doc_name} p.{retrieved[0].chunk.page_number}"
                if retrieved else "None"
            ),
            "retrieval_latency_ms": round(retrieval_latency_ms, 2),
        }

        for k in k_values:
            row[f"recall@{k}"] = calculate_recall_at_k(retrieved, expected_doc, expected_pages, k=k)
            row[f"mrr@{k}"] = calculate_mrr_at_k(retrieved, expected_doc, expected_pages, k=k)
            row[f"ndcg@{k}"] = calculate_ndcg_at_k(retrieved, expected_doc, expected_pages, k=k)

        if answer_mode:
            answer_start = time.perf_counter()
            response = _answer(query, retrieved)
            answer_latency_ms = (time.perf_counter() - answer_start) * 1000

            if response is not None:
                row["abstained"] = bool(response.abstained)
                # The agent may retrieve additional chunks through query expansion;
                # grounding must be checked against the chunks the answer actually used.
                citation_sources = response.retrieved_chunks or retrieved
                row["citation_precision"] = calculate_citation_precision(
                    response.citations, citation_sources
                )
                row["citation_count"] = len(response.citations)
                row["answer_excerpt"] = (response.answer or "")[:500]
                row["latency_ms"] = round(retrieval_latency_ms + answer_latency_ms, 2)

                reference_answer = item.get("ground_truth_answer")
                if reference_answer and not response.abstained:
                    row["answer_f1"] = calculate_token_f1(response.answer, reference_answer)

        per_query_details.append(row)

    # ------------------------------------------------------------------
    # Out-of-scope queries: abstention accuracy (legacy generator or answer_fn)
    # ------------------------------------------------------------------
    abstain_results: List[float] = []
    if (answer_fn is not None or rag_generator is not None) and out_of_scope_items:
        for oos in out_of_scope_items:
            retrieval_start = time.perf_counter()
            retrieved = retriever.search(oos["question"], top_k=min(5, max_k))
            retrieval_latency_ms = (time.perf_counter() - retrieval_start) * 1000

            answer_start = time.perf_counter()
            response = _answer(oos["question"], retrieved)
            answer_latency_ms = (time.perf_counter() - answer_start) * 1000

            row = {
                "id": oos.get("id"),
                "bucket": oos.get("bucket", "out_of_scope"),
                "scope": "out_of_scope",
                "question": oos["question"],
                "expected": "Abstain",
                "retrieved_top1": (
                    f"{retrieved[0].chunk.doc_name} p.{retrieved[0].chunk.page_number}"
                    if retrieved else "None"
                ),
                "retrieval_latency_ms": round(retrieval_latency_ms, 2),
            }

            if response is not None:
                row["abstained"] = bool(response.abstained)
                row["answer_excerpt"] = (response.answer or "")[:500]
                row["latency_ms"] = round(retrieval_latency_ms + answer_latency_ms, 2)
                passed = evaluate_abstention(
                    should_abstain=True,
                    actually_abstained=response.abstained,
                )
                abstain_results.append(1.0 if passed else 0.0)

            per_query_details.append(row)

    # ------------------------------------------------------------------
    # Aggregate metrics
    # ------------------------------------------------------------------
    in_scope_rows = [row for row in per_query_details if row["scope"] == "in_scope"]
    aggregate_metrics = _aggregate_rows(in_scope_rows, k_values)

    aggregate_metrics["abstention_accuracy"] = _average(abstain_results)
    aggregate_metrics["total_queries"] = len(dataset)
    aggregate_metrics["in_scope_queries"] = len(in_scope_items)
    aggregate_metrics["out_of_scope_queries"] = len(out_of_scope_items)
    aggregate_metrics["answer_mode"] = answer_mode
    aggregate_metrics["p95_latency_ms"] = _p95(
        [row["latency_ms"] for row in per_query_details if "latency_ms" in row]
    )

    bucket_metrics: Dict[str, Dict[str, Any]] = {}
    for bucket in sorted({row["bucket"] for row in in_scope_rows}):
        bucket_rows = [row for row in in_scope_rows if row["bucket"] == bucket]
        bucket_metrics[bucket] = _aggregate_rows(bucket_rows, k_values)
    aggregate_metrics["bucket_metrics"] = bucket_metrics

    # ------------------------------------------------------------------
    # Markdown report
    # ------------------------------------------------------------------
    lines = [
        "# Retrieval & RAG Benchmark Report",
        "",
        "## Summary Metrics",
        f"- **Total Test Queries**: {len(dataset)}",
        f"- **In-Scope Queries**: {len(in_scope_items)}",
        f"- **Out-of-Scope Queries**: {len(out_of_scope_items)}",
        "",
        "| Metric | Score | Target |",
        "|---|---|---|",
    ]

    for k in k_values:
        score_pct = f"{aggregate_metrics[f'recall@{k}'] * 100:.1f}%"
        lines.append(f"| **Recall@{k}** | {score_pct} | ≥ 70% |")

    for k in k_values:
        mrr = aggregate_metrics[f"mrr@{k}"]
        ndcg = aggregate_metrics[f"ndcg@{k}"]
        lines.append(f"| **MRR@{k}** | {mrr:.4f} | — |")
        lines.append(f"| **nDCG@{k}** | {ndcg:.4f} | — |")

    if aggregate_metrics["citation_precision"] is not None:
        lines.append(
            f"| **Citation Precision** | {aggregate_metrics['citation_precision'] * 100:.1f}% | ≥ 95% |"
        )
    if aggregate_metrics["answer_f1"] is not None:
        lines.append(f"| **Answer F1** | {aggregate_metrics['answer_f1']:.4f} | — |")
    if aggregate_metrics["in_scope_abstention_rate"] is not None:
        lines.append(
            f"| **In-Scope Abstention Rate** | {aggregate_metrics['in_scope_abstention_rate'] * 100:.1f}% | Thấp |"
        )
    if aggregate_metrics["abstention_accuracy"] is not None:
        abs_pct = f"{aggregate_metrics['abstention_accuracy'] * 100:.1f}%"
        lines.append(f"| **Abstention Accuracy** | {abs_pct} | ≥ 90% |")
    if aggregate_metrics["mean_latency_ms"] is not None:
        lines.append(f"| **Mean Latency** | {aggregate_metrics['mean_latency_ms']:.1f} ms | — |")
    if aggregate_metrics["p95_latency_ms"] is not None:
        lines.append(f"| **p95 Latency** | {aggregate_metrics['p95_latency_ms']:.1f} ms | — |")

    if bucket_metrics:
        lines.extend(
            [
                "",
                "## Per-Bucket Metrics",
                "",
                "| Bucket | Queries | Recall@5 | MRR@5 | nDCG@5 | Citation Precision | Answer F1 |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        bucket_k = 5 if 5 in k_values else k_values[-1]
        for bucket, metrics in bucket_metrics.items():
            citation = metrics.get("citation_precision")
            answer_f1 = metrics.get("answer_f1")
            lines.append(
                "| {bucket} | {count} | {recall:.4f} | {mrr:.4f} | {ndcg:.4f} | {citation} | {f1} |".format(
                    bucket=bucket,
                    count=metrics["num_queries"],
                    recall=metrics[f"recall@{bucket_k}"],
                    mrr=metrics[f"mrr@{bucket_k}"],
                    ndcg=metrics[f"ndcg@{bucket_k}"],
                    citation="—" if citation is None else f"{citation * 100:.1f}%",
                    f1="—" if answer_f1 is None else f"{answer_f1:.4f}",
                )
            )

    aggregate_metrics["markdown_report"] = "\n".join(lines)
    aggregate_metrics["per_query"] = per_query_details

    if output_json:
        output_path = Path(output_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "summary": {
                key: value
                for key, value in aggregate_metrics.items()
                if key not in {"markdown_report", "per_query"}
            },
            "per_query": per_query_details,
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

    return aggregate_metrics
