"""Evaluation and benchmarking module for Document Q&A Assistant."""

from src.eval.metrics import calculate_recall_at_k, evaluate_abstention
from src.eval.runner import run_benchmark

__all__ = ["calculate_recall_at_k", "evaluate_abstention", "run_benchmark"]
