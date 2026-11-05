"""Chit-chat detection and LLM intent classification used by the router node."""

import json
import logging
import re
from typing import Optional

from src.rag.agent_base import AgentBaseMixin

logger = logging.getLogger(__name__)


class ChitchatMixin(AgentBaseMixin):
    """Greeting / social-intent fast path with an LLM intent-classifier fallback."""

    CHITCHAT_PATTERNS = [
        (
            r"^(?:hello|hi|hey|halo|howdy)(?:\s+(?:there|bot|assistant|friend))?[\s\.\?!]*$|^(?:good\s+(?:morning|afternoon|evening|day))[\s\.\?!]*$",
            (
                "Hello! I am your Technical Document Q&A Assistant (Document Q&A Assistant).\n\n"
                "I can help you search, analyze technical specifications, verify engineering procedures, "
                "and provide accurate page citations directly from your uploaded documents (PDF, DOCX, TXT, OCR images).\n\n"
                "What technical information or document would you like to explore today?"
            )
        ),
        (
            r"^(?:xin\s+)?chào(?:\s+(?:bạn|trợ\s+lý|bot|ad|anh|chị|em|mọi\s+người))?[\s\.\?!]*$|^(?:hé\s+lô|alo)[\s\.\?!]*$|^(?:chào\s+buổi\s+(?:sáng|trưa|chiều|tối)|chúc\s+buổi\s+(?:sáng|trưa|chiều|tối))[\s\.\?!]*$",
            (
                "Xin chào! Tôi là Trợ lý Hỏi đáp Tài liệu Kỹ thuật (Document Q&A Assistant).\n\n"
                "Tôi có thể giúp bạn tra cứu, giải đáp thông số, quy trình kỹ thuật và trích dẫn nguồn số trang chính xác từ các tài liệu bạn đã tải lên (PDF, DOCX, TXT, Hình ảnh OCR).\n\n"
                "Bạn cần tìm hiểu hoặc kiểm tra thông tin gì trong tài liệu hôm nay?"
            )
        ),
        (
            r"^(?:(?:how\s+(?:can|do)\s+you\s+(?:help|assist)(?:\s+me)?)|(?:what\s+(?:can\s+you\s+do|do\s+you\s+do|are\s+your\s+(?:capabilities|functions|features)))|(?:can\s+you\s+help(?:\s+me)?)|(?:who\s+are\s+you)|(?:what\s+is\s+your\s+(?:purpose|role|job))|(?:how\s+(?:does\s+this\s+work|do\s+i\s+use\s+(?:this|you)|to\s+use(?:\s+this)?))|(?:help(?:\s+me)?)|(?:guide(?:\s+me)?)|(?:(?:tell\s+me\s+about|introduce)\s+yourself))[\s\.\?!]*$",
            (
                "I am a specialized Technical Document Q&A Assistant.\n\n"
                "Here is how I can help you:\n"
                "1. **Document Q&A & Search:** Analyze technical procedures, standards, and engineering data from your uploaded files (PDF, DOCX, TXT, OCR images).\n"
                "2. **Exact Citations & Page References:** Every answer is backed by exact document names and page numbers for verifiable audit trails.\n"
                "3. **Engineering Calculations:** Guide step-by-step calculations (e.g., Reynolds numbers, head loss, ISO hydraulic standards) based on document formulas.\n"
                "4. **Hallucination Prevention:** If the answer is not supported by your documents, I will explicitly abstain rather than speculate.\n\n"
                "Feel free to ask any question about your uploaded documents!"
            )
        ),
        (
            r"^(?:(?:bạn\s+(?:có\s+thể\s+làm\s+gì|làm\s+được\s+gì|giúp\s+(?:được\s+)?gì(?:\s+cho\s+tôi)?|giúp\s+gì\s+được(?:\s+cho\s+tôi)?|là\s+ai|có\s+chức\s+năng\s+gì|dùng\s+để\s+làm\s+gì))|(?:chức\s+năng\s+của\s+bạn(?:\s+là\s+gì)?)|(?:hướng\s+dẫn(?:\s+(?:tôi\s+)?(?:cách\s+)?(?:dùng|sử\s+dụng))?)|(?:trợ\s+giúp)|(?:giới\s+thiệu(?:\s+(?:về\s+bạn|bản\s+thân))?))[\s\.\?!]*$",
            (
                "Tôi là Trợ lý AI Hỏi đáp Kỹ thuật chuyên sâu.\n\n"
                "Tôi có thể giúp bạn:\n"
                "1. **Tra cứu & Hỏi đáp tài liệu:** Tìm kiếm và giải đáp thông số, quy trình kỹ thuật từ các tài liệu bạn đã tải lên (PDF, DOCX, TXT, OCR ảnh).\n"
                "2. **Trích dẫn nguồn & Số trang chính xác:** Cung cấp dẫn chứng rõ ràng kèm tên tài liệu và số trang cho từng câu trả lời.\n"
                "3. **Tính toán kỹ thuật:** Hướng dẫn giải chi tiết các bài toán kỹ thuật theo công thức trong tài liệu (chuẩn số Reynolds, tổn thất cột áp, ISO thủy lực...).\n"
                "4. **Chống suy đoán sai lệch:** Nếu câu hỏi không có căn cứ trong tài liệu, tôi sẽ từ chối để đảm bảo độ tin cậy kỹ thuật.\n\n"
                "Bạn có thể đặt câu hỏi về bất kỳ tài liệu nào đã tải lên!"
            )
        ),
        (
            r"^(?:thanks?(?:\s+a\s+lot|\s+so\s+much)?|thank\s+you(?:\s+very\s+much|\s+so\s+much)?)[\s\.\?!]*$",
            (
                "You're very welcome! If you have any further questions about your documents, feel free to ask."
            )
        ),
        (
            r"^(?:cảm\s+ơn|cám\s+ơn|thanks?|thank\s+you)(?:\s+(?:bạn|nhiều|rất\s+nhiều|nhé|nha|trợ\s+lý|bot))*\s*[\s\.\?!]*$",
            (
                "Rất vui được hỗ trợ bạn! Nếu bạn có thêm câu hỏi kỹ thuật nào về tài liệu, hãy cứ đặt câu hỏi nhé."
            )
        ),
        (
            r"^(?:goodbye|bye(?:\s+bye)?|see\s+you(?:\s+later|\s+soon)?|have\s+a\s+(?:good|nice)\s+day)[\s\.\?!]*$",
            (
                "Goodbye! Have a great day and see you next time you need to look up documentation."
            )
        ),
        (
            r"^(?:tạm\s+biệt|bye|goodbye|hẹn\s+gặp\s+lại|bai\s+bai)[\s\.\?!]*$",
            (
                "Tạm biệt bạn! Chúc bạn làm việc hiệu quả và hẹn gặp lại khi bạn cần tra cứu tài liệu!"
            )
        ),
    ]

    GREETING_PREFIX_PATTERN = re.compile(
        r"^(?:xin\s+chào|chào\s+(?:bạn|trợ\s+lý|bot|ad|anh|chị|em|mọi\s+người)?|hello|hi|hey|halo|hé\s+lô|alo|good\s+morning|good\s+afternoon|good\s+evening)\s*[,.:;!\-–—]*\s*",
        re.IGNORECASE
    )

    def _detect_chitchat(self, text: str) -> Optional[str]:
        """Detect if user query is a greeting, introduction, thanks, or chitchat using fast-path regex."""
        clean = text.strip().lower()
        clean_unaccented = self._remove_accents(clean)
        for pattern, reply in self.CHITCHAT_PATTERNS:
            if re.match(pattern, clean, re.IGNORECASE) or re.match(pattern, clean_unaccented, re.IGNORECASE):
                return reply
        return None

    def _classify_intent_with_llm(self, question: str) -> Optional[str]:
        """Classify user intent using LLM when fast-path regex patterns do not match.

        Returns chitchat reply string if intent is CHITCHAT, else None if technical query.
        """
        if self.llm_client is None:
            return None

        prompt = (
            "Bạn là bộ phân loại ý định (Intent Classifier) cho Trợ lý Hỏi đáp Tài liệu Kỹ thuật (Document Q&A Assistant).\n"
            "Hãy phân tích câu hỏi/yêu cầu sau của người dùng và xác định xem người dùng muốn:\n"
            "1. 'CHITCHAT': Chào hỏi, cảm ơn, khen ngợi, hỏi bạn là ai, hỏi bot có thể làm gì, cách sử dụng trợ lý, năng lực của hệ thống, hoặc câu hỏi giao tiếp xã giao không cần đọc tài liệu kỹ thuật.\n"
            "2. 'TECHNICAL_QUERY': Câu hỏi tra cứu dữ liệu, tiêu chuẩn kỹ thuật (ISO, TCVN), thông số, quy trình, công thức tính toán hoặc yêu cầu giải bài toán kỹ thuật từ tài liệu.\n\n"
            f"Câu hỏi của người dùng: \"{question}\"\n\n"
            "Trả về DUY NHẤT một chuỗi JSON hợp lệ không bọc trong markdown code blocks, theo định dạng:\n"
            "{\"intent\": \"CHITCHAT\" hoặc \"TECHNICAL_QUERY\", \"reply\": \"<Nếu là CHITCHAT, hãy trả lời ngắn gọn, lịch sự, chuyên nghiệp bằng đúng ngôn ngữ của người dùng (Anh/Việt) giới thiệu năng lực hỗ trợ tài liệu kỹ thuật. Nếu là TECHNICAL_QUERY thì để null>\"}"
        )

        try:
            raw = self._call_llm(prompt)
            if not raw:
                return None

            clean_json = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
            clean_json = re.sub(r"\s*```$", "", clean_json)
            start = clean_json.find("{")
            end = clean_json.rfind("}")
            if start != -1 and end != -1:
                clean_json = clean_json[start : end + 1]

            data = json.loads(clean_json)
            intent = str(data.get("intent", "")).upper()
            if intent == "CHITCHAT":
                reply = data.get("reply")
                if reply and isinstance(reply, str) and len(reply.strip()) > 5:
                    return reply.strip()
                return (
                    "Tôi là Trợ lý AI Hỏi đáp Kỹ thuật chuyên sâu. Tôi có thể giúp bạn tra cứu, "
                    "giải đáp thông số, quy trình và cung cấp trích dẫn chính xác từ các tài liệu bạn tải lên."
                )
            return None
        except Exception as e:
            logger.warning(f"LLM intent classification failed: {e}")
            return None
