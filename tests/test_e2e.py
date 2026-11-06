# tests/test_e2e.py
import pytest
from pathlib import Path
from src.ingestion.pdf_extractor import extract_pages_from_pdf
from src.ingestion.chunker import chunk_document
from src.retrieval.local import LocalRetriever
from src.vector_store.embedding import EmbeddingModel
from src.vector_store.qdrant_store import QdrantVectorStore
from src.eval.runner import run_benchmark

def test_full_pipeline_on_sample_docs(tmp_path):
    from tests.fixtures.sample_docs import generate_sample_documents
    generate_sample_documents(output_dir=str(tmp_path))
    pdf_path = str(tmp_path / "pump_maintenance_guide.pdf")
    assert Path(pdf_path).exists(), "Sample doc must exist"

    pages = extract_pages_from_pdf(pdf_path)
    assert len(pages) >= 2

    chunks = chunk_document(pages)
    assert len(chunks) > 0

    embedder = EmbeddingModel("all-MiniLM-L6-v2")
    store = QdrantVectorStore(storage_path=str(tmp_path / "e2e_qdrant"), collection_name="e2e")
    retriever = LocalRetriever(embedder, store)
    retriever.index_chunks(chunks)

    # Benchmark run
    report = run_benchmark(retriever, ground_truth_file="tests/fixtures/sample_ground_truth.json", k_values=[1, 3, 5])
    assert report["recall@5"] >= 0.7
    store.close()

