"""Standalone script to index sample documents and run the evaluation benchmark.

The benchmark uses an isolated temporary Qdrant collection so it never touches the
application's production index. It evaluates hybrid retrieval by default and can
optionally run the full AgenticRAG pipeline (mock or live LLM).
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

# Set offline mode default for huggingface hub if not explicitly overridden
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

# Ensure root package is discoverable when script is run directly
_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from src.config import settings
from src.eval.runner import run_benchmark
from src.ingestion.chunker import chunk_document
from src.ingestion.ocr_engine import OcrEngine
from src.ingestion.pdf_extractor import extract_pages_from_pdf
from src.ingestion.tokenization import get_chunk_token_limit
from src.rag.agent import AgenticRAG
from src.retrieval.bm25 import BM25Retriever
from src.retrieval.hybrid import HybridRetriever
from src.retrieval.local import LocalRetriever
from src.retrieval.reranker import CrossEncoderReranker
from src.vector_store.embedding import EmbeddingModel
from src.vector_store.qdrant_store import QdrantVectorStore


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark hybrid retrieval and AgenticRAG on the sample corpus."
    )
    parser.add_argument(
        "--ground-truth",
        default="data/eval/ground_truth.json",
        help="Path to the ground truth JSON file.",
    )
    parser.add_argument(
        "--k-values",
        default="1,3,5,10",
        help="Comma-separated K values for Recall/MRR/nDCG.",
    )
    parser.add_argument(
        "--collection",
        default="benchmark_docs",
        help="Temporary Qdrant collection name.",
    )
    parser.add_argument(
        "--provider",
        choices=["mock", "gemini", "openai"],
        default="mock",
        help="LLM provider for end-to-end evaluation (default: mock, no API calls).",
    )
    parser.add_argument(
        "--no-agent",
        action="store_true",
        help="Run retrieval-only evaluation (no answer generation).",
    )
    parser.add_argument(
        "--no-reranker",
        action="store_true",
        help="Disable the cross-encoder reranker when running the agent.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write the full JSON report.",
    )
    return parser.parse_args()


def _build_llm_client(provider: str):
    if provider == "gemini":
        if not settings.gemini_api_key:
            raise SystemExit(
                "GEMINI_API_KEY is empty. Use --provider mock or set the key in .env."
            )
        from google import genai

        return genai.Client(api_key=settings.gemini_api_key)

    if provider == "openai":
        if not settings.openai_api_key:
            raise SystemExit(
                "OPENAI_API_KEY is empty. Use --provider mock or set the key in .env."
            )
        from openai import OpenAI

        return OpenAI(api_key=settings.openai_api_key)

    return None


def main() -> None:
    args = _parse_args()
    k_values = [int(value.strip()) for value in args.k_values.split(",") if value.strip()]

    print("=" * 60)
    print("DOCUMENT Q&A ASSISTANT — RETRIEVAL & RAG BENCHMARK")
    print("=" * 60)

    ocr_engine = OcrEngine()
    embedder = EmbeddingModel(
        settings.embedding_model,
        device=settings.embedding_device or None,
        max_seq_length=settings.embedding_max_seq_length,
        batch_size=settings.embedding_batch_size,
    )
    chunk_token_limit = get_chunk_token_limit(
        embedder.max_seq_length,
        settings.chunk_size_tokens,
    )

    with tempfile.TemporaryDirectory(prefix="rag_eval_") as temp_dir:
        store = QdrantVectorStore(
            storage_path=str(Path(temp_dir) / "qdrant"),
            collection_name=args.collection,
            vector_size=embedder.dimension,
            url=None,
            api_key=None,
        )
        try:
            dense_retriever = LocalRetriever(embedder, store)
            sparse_retriever = BM25Retriever()
            retriever = HybridRetriever(
                dense_retriever=dense_retriever,
                sparse_retriever=sparse_retriever,
                rrf_k=settings.hybrid_rrf_k,
            )

            # Ingest the generated sample corpus into the isolated collection.
            from scripts.generate_sample_docs import generate_sample_documents

            generate_sample_documents(output_dir=temp_dir)
            sample_files = [
                Path(temp_dir) / "pump_maintenance_guide.pdf",
                Path(temp_dir) / "scanned_circuit_diagram.pdf",
            ]

            total_chunks = 0
            for pdf_file in sample_files:
                if not pdf_file.exists():
                    print(f"Warning: File not found: {pdf_file}")
                    continue

                pages = extract_pages_from_pdf(str(pdf_file), ocr_engine=ocr_engine)
                chunks = chunk_document(
                    pages,
                    chunk_size=settings.chunk_size,
                    chunk_overlap=settings.chunk_overlap,
                    tokenizer=embedder.tokenizer,
                    max_tokens=chunk_token_limit,
                    overlap_tokens=settings.chunk_overlap_tokens,
                )
                count = retriever.index_chunks(chunks)
                total_chunks += count
                print(f"-> Ingested {pdf_file.name}: {len(pages)} pages, {count} chunks indexed.")

            print(f"\nTotal chunks in isolated collection: {total_chunks}")

            answer_fn = None
            agent = None
            if not args.no_agent:
                if args.provider == "mock":
                    print(
                        "Note: --provider mock uses deterministic fallback generation; "
                        "answer metrics are a plumbing smoke test, not a quality baseline."
                    )
                llm_client = _build_llm_client(args.provider)
                reranker = (
                    None
                    if args.no_reranker
                    else CrossEncoderReranker(model_name=settings.reranker_model)
                )
                model_name = settings.gemini_model if args.provider == "gemini" else None
                agent = AgenticRAG(
                    retriever=retriever,
                    reranker=reranker,
                    llm_client=llm_client,
                    provider=args.provider,
                    model_name=model_name,
                    min_relevance_score=settings.min_relevance_score,
                )
                answer_fn = agent.answer

            print(f"\nRunning benchmark on {args.ground_truth} ...\n")
            report = run_benchmark(
                retriever=retriever,
                ground_truth_file=args.ground_truth,
                k_values=k_values,
                answer_fn=answer_fn,
                output_json=args.output,
            )
            print(report["markdown_report"])

            if args.output:
                print(f"\nFull JSON report written to: {args.output}")
        finally:
            store.close()


if __name__ == "__main__":
    main()
