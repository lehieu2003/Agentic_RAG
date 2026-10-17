"""Standalone script to index sample documents and run evaluation benchmark."""

from pathlib import Path
from src.eval.runner import run_benchmark
from src.ingestion.chunker import chunk_document
from src.ingestion.ocr_engine import OcrEngine
from src.ingestion.pdf_extractor import extract_pages_from_pdf
from src.rag.generator import RAGGenerator
from src.retrieval.local import LocalRetriever
from src.vector_store.embedding import EmbeddingModel
from src.vector_store.qdrant_store import QdrantVectorStore


def main():
    print("=" * 60)
    print("DOCUMENT Q&A ASSISTANT — RETRIEVAL & RAG BENCHMARK")
    print("=" * 60)

    # 1. Initialize components
    ocr_engine = OcrEngine()
    embedder = EmbeddingModel("all-MiniLM-L6-v2")
    store = QdrantVectorStore(storage_path="data/qdrant_storage", collection_name="benchmark_docs")
    retriever = LocalRetriever(embedder, store)
    generator = RAGGenerator(provider="mock")

    # 2. Ingest sample documents
    sample_files = [
        "sample_docs/pump_maintenance_guide.pdf",
        "sample_docs/scanned_circuit_diagram.pdf"
    ]

    total_chunks = 0
    for pdf_file in sample_files:
        if not Path(pdf_file).exists():
            print(f"Warning: File not found: {pdf_file}")
            continue

        pages = extract_pages_from_pdf(pdf_file, ocr_engine=ocr_engine)
        chunks = chunk_document(pages)
        count = retriever.index_chunks(chunks)
        total_chunks += count
        print(f"-> Ingested {pdf_file}: {len(pages)} pages, {count} chunks indexed.")

    print(f"\nTotal chunks in vector store: {total_chunks}")
    print("\nRunning benchmark on data/eval/ground_truth.json ...\n")

    # 3. Run Benchmark
    report = run_benchmark(
        retriever=retriever,
        ground_truth_file="data/eval/ground_truth.json",
        k_values=[1, 3, 5, 10],
        rag_generator=generator
    )

    print(report["markdown_report"])
    store.close()


if __name__ == "__main__":
    main()

