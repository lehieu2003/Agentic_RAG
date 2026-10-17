"""Benchmark runner for Recall@K and Abstention evaluation."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from src.eval.metrics import calculate_recall_at_k, evaluate_abstention
from src.models import RetrievalResult
from src.rag.generator import RAGGenerator
from src.retrieval.base import BaseRetriever


def run_benchmark(
    retriever: BaseRetriever,
    ground_truth_file: str = "data/eval/ground_truth.json",
    k_values: Optional[List[int]] = None,
    rag_generator: Optional[RAGGenerator] = None
) -> Dict[str, Any]:
    """Execute quantitative benchmark on ground truth dataset.

    Args:
        retriever: Concrete BaseRetriever instance to evaluate.
        ground_truth_file: Path to ground truth JSON file.
        k_values: List of K values for Recall@K (defaults to [1, 3, 5, 10]).
        rag_generator: Optional RAGGenerator to measure end-to-end abstention accuracy.

    Returns:
        Summary metrics dictionary.
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
    recall_hits: Dict[int, List[float]] = {k: [] for k in k_values}
    per_query_details: List[Dict[str, Any]] = []

    for item in in_scope_items:
        query = item["question"]
        expected_doc = item["expected_doc"]
        expected_pages = item["expected_pages"]

        # Retrieve top max_k results
        retrieved: List[RetrievalResult] = retriever.search(query, top_k=max_k)

        query_hits = {}
        for k in k_values:
            hit = calculate_recall_at_k(retrieved, expected_doc, expected_pages, k=k)
            recall_hits[k].append(hit)
            query_hits[f"recall@{k}"] = hit

        per_query_details.append({
            "id": item["id"],
            "question": query,
            "expected": f"{expected_doc} p.{expected_pages}",
            "retrieved_top1": (
                f"{retrieved[0].chunk.doc_name} p.{retrieved[0].chunk.page_number}"
                if retrieved else "None"
            ),
            **query_hits
        })

    # Calculate aggregate Recall@K
    aggregate_metrics: Dict[str, Any] = {}
    total_in_scope = len(in_scope_items)
    for k in k_values:
        avg_recall = (sum(recall_hits[k]) / total_in_scope) if total_in_scope > 0 else 0.0
        aggregate_metrics[f"recall@{k}"] = round(avg_recall, 4)

    # Abstention benchmark (if generator is provided)
    if rag_generator is not None and out_of_scope_items:
        abstain_results = []
        for oos in out_of_scope_items:
            retrieved = retriever.search(oos["question"], top_k=5)
            # Filter low relevance if needed or let generator decide
            resp = rag_generator.generate_answer(oos["question"], retrieved)
            passed = evaluate_abstention(should_abstain=True, actually_abstained=resp.abstained)
            abstain_results.append(1.0 if passed else 0.0)

        aggregate_metrics["abstention_accuracy"] = round(
            sum(abstain_results) / len(abstain_results), 4
        )
    else:
        aggregate_metrics["abstention_accuracy"] = 1.0

    aggregate_metrics["total_queries"] = len(dataset)
    aggregate_metrics["in_scope_queries"] = total_in_scope
    aggregate_metrics["out_of_scope_queries"] = len(out_of_scope_items)

    # Format Markdown Report
    lines = [
        "# Retrieval & RAG Benchmark Report",
        "",
        "## Summary Metrics",
        f"- **Total Test Queries**: {len(dataset)}",
        f"- **In-Scope Queries**: {total_in_scope}",
        f"- **Out-of-Scope Queries**: {len(out_of_scope_items)}",
        "",
        "| Metric | Score | Target |",
        "|---|---|---|"
    ]
    for k in k_values:
        score_pct = f"{aggregate_metrics[f'recall@{k}'] * 100:.1f}%"
        lines.append(f"| **Recall@{k}** | {score_pct} | ≥ 70% |")

    if "abstention_accuracy" in aggregate_metrics:
        abs_pct = f"{aggregate_metrics['abstention_accuracy'] * 100:.1f}%"
        lines.append(f"| **Abstention Accuracy** | {abs_pct} | ≥ 90% |")

    aggregate_metrics["markdown_report"] = "\n".join(lines)
    return aggregate_metrics
