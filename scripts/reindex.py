"""Reindex every raw upload into a Qdrant collection for the configured model.

Use this after changing EMBEDDING_MODEL or the embedding dimension. The script is
explicitly destructive only when --recreate --yes is passed; otherwise it appends
to the existing collection.
"""

import argparse
import sys
import unicodedata
from pathlib import Path
from typing import List

# Ensure root package is discoverable when script is run directly
_repo_root = str(Path(__file__).resolve().parent.parent)
if _repo_root not in sys.path:
    sys.path.insert(0, _repo_root)

from src.config import settings
from src.ingestion.chunker import chunk_document
from src.ingestion.document_extractor import extract_pages_from_document
from src.ingestion.ocr_engine import OcrEngine
from src.ingestion.tokenization import get_chunk_token_limit
from src.vector_store.embedding import EmbeddingModel
from src.vector_store.qdrant_store import QdrantVectorStore

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reindex raw uploads with the configured embedding model."
    )
    parser.add_argument(
        "--upload-dir",
        default=settings.upload_dir,
        help=f"Directory containing raw uploads (default: {settings.upload_dir}).",
    )
    parser.add_argument(
        "--collection",
        default=settings.qdrant_collection,
        help=f"Target Qdrant collection (default: {settings.qdrant_collection}).",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Delete and recreate the target collection before indexing.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Required confirmation when --recreate is used.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only extract and count chunks; do not write to Qdrant.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    upload_dir = Path(args.upload_dir)

    if args.recreate and not args.yes:
        raise SystemExit("Refusing to delete a collection without --yes.")

    if not upload_dir.exists():
        raise SystemExit(f"Upload directory not found: {upload_dir}")

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
    ocr_engine = OcrEngine()

    files: List[Path] = sorted(
        (
            path
            for path in upload_dir.iterdir()
            if path.is_file()
            and not path.name.startswith(".")
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ),
        key=lambda path: path.name.lower(),
    )

    print(f"Embedding model : {settings.embedding_model}")
    print(f"Dimension       : {embedder.dimension}")
    print(f"Chunk tokens    : {chunk_token_limit} (overlap {settings.chunk_overlap_tokens})")
    print(f"Uploads         : {len(files)} file(s) in {upload_dir}")
    print(f"Collection      : {args.collection}")
    print(f"Dry run         : {args.dry_run}")

    if not files:
        print("Nothing to reindex.")
        return

    store = None
    if not args.dry_run:
        store = QdrantVectorStore(
            storage_path=settings.qdrant_path,
            collection_name=args.collection,
            vector_size=embedder.dimension,
            url=settings.qdrant_url if settings.qdrant_url else None,
            api_key=settings.qdrant_api_key if settings.qdrant_api_key else None,
            recreate=args.recreate,
        )
        if settings.qdrant_url and store.url is None:
            print(
                "WARNING: Qdrant Cloud was unreachable; the store fell back to "
                f"local path '{settings.qdrant_path}'. Reindex did NOT touch the cloud."
            )

    total_chunks = 0
    failed_files: List[str] = []
    try:
        for file_path in files:
            try:
                pages = extract_pages_from_document(
                    str(file_path),
                    ocr_engine=ocr_engine,
                )
                safe_name = unicodedata.normalize("NFC", file_path.name)
                for page in pages:
                    page["doc_name"] = safe_name

                chunks = chunk_document(
                    pages,
                    chunk_size=settings.chunk_size,
                    chunk_overlap=settings.chunk_overlap,
                    tokenizer=embedder.tokenizer,
                    max_tokens=chunk_token_limit,
                    overlap_tokens=settings.chunk_overlap_tokens,
                )
                total_chunks += len(chunks)

                if store is not None:
                    vectors = embedder.embed_texts([chunk.text for chunk in chunks])
                    store.upsert_chunks_with_vectors(chunks, vectors)

                print(f"  OK   {file_path.name}: {len(pages)} pages, {len(chunks)} chunks")
            except Exception as exc:
                failed_files.append(file_path.name)
                print(f"  FAIL {file_path.name}: {exc}")
    finally:
        if store is not None:
            store.close()

    print(f"\nTotal chunks: {total_chunks}")
    if failed_files:
        print(f"Failed files ({len(failed_files)}): {', '.join(failed_files)}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
