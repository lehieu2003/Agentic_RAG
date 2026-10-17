"""Prompt templates and citation formatting rules for technical document Q&A."""

from typing import List
from src.models import RetrievalResult

ABSTAIN_PHRASE = "Tôi không tìm thấy thông tin này trong tài liệu được cung cấp."


def build_rag_prompt(question: str, chunks: List[RetrievalResult]) -> str:
    """Format technical document context and question into a grounded system prompt.

    Args:
        question: The user's technical question.
        chunks: Retrieved context chunks.

    Returns:
        Formatted prompt string.
    """
    context_blocks: List[str] = []
    for r in chunks:
        block = f"[Tài liệu: {r.chunk.doc_name} | Trang: {r.chunk.page_number}]\n{r.chunk.text}"
        context_blocks.append(block)

    joined_context = "\n\n---\n\n".join(context_blocks) if context_blocks else "Không có tài liệu nào được tìm thấy."

    prompt = f"""Bạn là trợ lý hỏi đáp tài liệu kỹ thuật chính xác và đáng tin cậy.
Nhiệm vụ của bạn là trả lời câu hỏi của người dùng DỰA HOÀN TOÀN vào các đoạn trích từ tài liệu được cung cấp dưới đây.

CÁC NGUYÊN TẮC BẮT BUỘC:
1. TRÍCH DẪN NGUỒN (CITATIONS):
   - Mọi thông tin, số liệu kỹ thuật, hướng dẫn bạn đưa ra PHẢI kèm trích dẫn chính xác định dạng:
     [Tài liệu: <tên_file>, Trang <số_trang>]
   - Ví dụ: "Áp suất tối đa cho phép là 10 bar [Tài liệu: pump_manual.pdf, Trang 12]."

2. NGUYÊN TẮC TỪ CHỐI (ABSTENTION - TUYỆT ĐỐI KHÔNG SUY ĐOÁN/HALLUCINATE):
   - Nếu trong các đoạn trích dưới đây KHÔNG có đầy đủ thông tin để trả lời câu hỏi, bạn PHẢI trả lời chính xác câu sau và không giải thích thêm:
     "{ABSTAIN_PHRASE}"

DỮ LIỆU TÀI LIỆU CUNG CẤP:
{joined_context}

CÂU HỎI:
{question}

CÂU TRẢ LỜI:"""
    return prompt
