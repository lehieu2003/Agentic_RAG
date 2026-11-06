"""Document ingestion, listing, serving, and deletion routes.

Thin web adapters: request parsing, filename-shape validation, and response
building live here; the ingestion pipeline lives in
``src.application.ingestion_service``.
"""

import mimetypes
from pathlib import Path
from typing import Annotated, Any, Dict, List
import unicodedata

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from src.api.dependencies import get_ingestion_service
from src.application.ingestion_service import IngestionService
from src.models import FileSummary, UploadResponse

router = APIRouter()


@router.post(
    "/upload",
    response_model=UploadResponse,
    tags=["Tải lên tài liệu (Ingestion)"],
    summary="Tải lên tài liệu kỹ thuật để bóc tách text/OCR và đánh chỉ mục vector"
)
async def upload_document(
    file: Annotated[UploadFile, File(...)],
    ingestion: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> UploadResponse:
    """Tải lên tài liệu kỹ thuật (PDF, DOCX, TXT, PNG, JPG, JPEG). Hệ thống sẽ:
    1. Kiểm tra định dạng hỗ trợ.
    2. Chống nạp trùng lặp dựa trên tên file trong thư mục lưu trữ.
    3. Lưu trữ file gốc vĩnh viễn vào data/uploads/.
    4. Trích xuất text kỹ thuật số hoặc OCR tuỳ định dạng.
    5. Phân đoạn ngữ nghĩa (chunking) bảo toàn số trang.
    6. Sinh embedding và lưu trữ vào Qdrant.
    """
    return ingestion.ingest(filename=file.filename, fileobj=file.file)

@router.get(
    "/files",
    response_model=List[FileSummary],
    tags=["Quản lý tài liệu (Files)"],
    summary="Danh sách tất cả các tài liệu đã được lưu trữ vĩnh viễn"
)
def list_files(
    ingestion: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> List[FileSummary]:
    """Liệt kê danh sách tài liệu đang thực sự được đánh chỉ mục trong hệ thống.

    Đây là endpoint chỉ đọc: file mồ côi hoặc file tạm đang upload sẽ bị bỏ qua
    nhưng không bị xoá. Việc dọn dẹp phải do một job bảo trì/reindex riêng thực hiện.
    """
    return ingestion.list_documents()

@router.api_route(
    "/files/{filename:path}",
    methods=["GET", "HEAD"],
    tags=["Quản lý tài liệu (Files)"],
    summary="Tải hoặc xem trực tiếp tài liệu gốc trên trình duyệt"
)
async def serve_file(
    filename: str,
    ingestion: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> FileResponse:
    """Phục vụ file tài liệu gốc để xem trực tiếp trên tab trình duyệt (hỗ trợ #page=N cho PDF)."""
    file_path = ingestion.find_document_path(filename)

    mime_type, _ = mimetypes.guess_type(str(file_path))
    mime_type = mime_type or "application/octet-stream"

    return FileResponse(
        path=str(file_path),
        media_type=mime_type,
        filename=unicodedata.normalize("NFC", file_path.name),
        content_disposition_type="inline"
    )

@router.delete(
    "/files/{filename:path}",
    tags=["Quản lý tài liệu (Files)"],
    summary="Xoá tài liệu khỏi hệ thống và vector database"
)
def delete_document(
    filename: str,
    ingestion: Annotated[IngestionService, Depends(get_ingestion_service)],
) -> Dict[str, Any]:
    """Xoá hoàn toàn tài liệu:
    1. Xoá tất cả vector và chunk trong Qdrant.
    2. Xoá chunk trong BM25.
    3. Xoá file vật lý trong data/uploads/.
    """
    raw_name = Path(filename).name
    if not raw_name or raw_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid filename")

    return ingestion.delete_document(filename)
