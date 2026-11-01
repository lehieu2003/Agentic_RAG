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
Nhiệm vụ của bạn là trả lời câu hỏi của người dùng DỰA VÀO các đoạn trích từ tài liệu được cung cấp dưới đây.

CÁC NGUYÊN TẮC BẮT BUỘC:
1. TRÍCH DẪN NGUỒN (CITATIONS):
   - Mọi thông tin, công thức, định nghĩa, thông số kỹ thuật, hướng dẫn bạn đưa ra PHẢI kèm trích dẫn chính xác định dạng:
     [Tài liệu: <tên_file>, Trang <số_trang>]
   - Ví dụ: "Áp suất tối đa cho phép là 10 bar [Tài liệu: pump_manual.pdf, Trang 12]."

2. HƯỚNG DẪN TÍNH TOÁN KỸ THUẬT (CALCULATION & FORMULA APPLICATION):
   - Khi câu hỏi yêu cầu tính toán dựa trên số liệu đầu vào của người dùng:
     a. Tìm công thức, định nghĩa hoặc nguyên lý trong tài liệu và trích dẫn rõ [Tài liệu: <tên_file>, Trang <số_trang>].
     b. Được phép áp dụng các hằng số vật lý/kỹ thuật tiêu chuẩn quốc tế và các công thức toán học/hình học phổ thông hỗ trợ khi thực hiện các phép tính theo công thức từ tài liệu.
     c. Trình bày lời giải từng bước rõ ràng: (1) Nêu công thức trích dẫn từ tài liệu, (2) Thế số và tính toán số học chi tiết, (3) Kết luận đáp số với đơn vị đo.
     d. Trích dẫn nguồn tài liệu ở phần nêu công thức và căn cứ lý thuyết.

3. NGUYÊN TẮC TỪ CHỐI (ABSTENTION) VÀ XỬ LÝ CÂU HỎI NHIỀU YÊU CẦU:
   - Nếu trong các đoạn trích dưới đây hoàn toàn KHÔNG có công thức, định nghĩa hay căn cứ nào để trả lời câu hỏi, bạn PHẢI trả lời chính xác câu sau và không giải thích thêm:
     "{ABSTAIN_PHRASE}"
   - Đối với câu hỏi gồm nhiều phần hoặc nhiều yêu cầu: Hãy giải quyết chi tiết từng phần có căn cứ và công thức trong tài liệu (kèm trích dẫn). Nếu một phần cụ thể nào đó thiếu dữ liệu hoặc bảng tra trong các đoạn trích dẫn, hãy nêu rõ thông tin còn thiếu của phần đó nhưng vẫn giải quyết đầy đủ các phần có căn cứ.

DỮ LIỆU TÀI LIỆU CUNG CẤP:
{joined_context}

CÂU HỎI:
{question}

CÂU TRẢ LỜI:"""
    return prompt

