"""Helpers for label-free / synthetic evaluation on the real upload corpus.

Two complementary methods are supported:

A. Synthetic QA generation: an LLM writes one question per source page. The page
   the question was generated from is the label, so Recall@K/MRR can be computed
   without hand-written ground truth.
B. LLM-as-judge: for each question, the passages returned by several retrieval
   configurations are pooled, shuffled, and graded blind (0/1/2). This yields
   graded precision/nDCG and per-question win rates without any labels.
"""

import json
import math
import random
import re
import threading
import time
import unicodedata
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

LLMFn = Callable[[str], str]

QA_PROMPT = """Bạn đang xây dựng bộ câu hỏi kiểm thử cho hệ thống tìm kiếm tài liệu kỹ thuật.

Tài liệu: {doc_name} — Trang {page}
--- NỘI DUNG TRANG ---
{text}
--- HẾT ---

Hãy viết MỘT câu hỏi tiếng Việt mà người dùng thực tế có thể hỏi, sao cho:
- Câu trả lời nằm cụ thể trong trang này (không phải kiến thức chung).
- Câu hỏi tự đứng được, KHÔNG nhắc tới "trang này", "tài liệu này", "đoạn trên".
- Diễn đạt lại bằng từ ngữ của bạn, KHÔNG chép nguyên văn câu trong tài liệu.
- Hỏi về một chi tiết rõ ràng (thông số, quy trình, định nghĩa, nguyên nhân, so sánh...).

Nếu trang chỉ là bìa, mục lục, tài liệu tham khảo, lời cảm ơn hoặc quá ít nội dung, đặt "skip": true.

Chỉ trả về JSON:
{{"skip": false, "question": "...", "answer": "câu trả lời ngắn dựa trên trang", "type": "factual|procedural|conceptual"}}"""

JUDGE_PROMPT = """Bạn là người chấm điểm độ liên quan cho hệ thống tìm kiếm tài liệu kỹ thuật.

Câu hỏi: {question}

Dưới đây là các đoạn văn được tìm thấy (thứ tự ngẫu nhiên):
{passages}

Chấm từng đoạn theo thang:
- 2: đoạn chứa trực tiếp thông tin trả lời câu hỏi.
- 1: đoạn liên quan chủ đề / trả lời được một phần nhưng chưa đủ.
- 0: không liên quan.

Chỉ trả về JSON dạng {{"grades": {{"P1": 0, "P2": 2, ...}}}} cho TẤT CẢ các đoạn."""


def nfc(text: str) -> str:
    """Normalize text to NFC so Vietnamese file names compare reliably."""
    return unicodedata.normalize("NFC", text or "")


def parse_json_object(raw: str) -> Optional[Dict[str, Any]]:
    """Extract the first JSON object from an LLM response (tolerates code fences)."""
    if not raw:
        return None
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


class RateLimiter:
    """Thread-safe limiter spacing calls to at most ``rpm`` requests per minute."""

    def __init__(self, rpm: float) -> None:
        self.interval = 60.0 / rpm if rpm and rpm > 0 else 0.0
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        if self.interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            slot = max(now, self._next)
            self._next = slot + self.interval
        if slot > now:
            time.sleep(slot - now)


_RETRY_IN = re.compile(r"retry in ([\d.]+)s", re.IGNORECASE)


def make_gemini_llm(api_key: str, model: str, rpm: float = 14, max_attempts: int = 6) -> LLMFn:
    """Return a rate-limited Gemini text function that honors server retry hints."""
    from google import genai

    client = genai.Client(api_key=api_key)
    limiter = RateLimiter(rpm)

    def _call(prompt: str) -> str:
        delay = 5.0
        last_error = ""
        for _ in range(max_attempts):
            limiter.wait()
            try:
                response = client.models.generate_content(model=model, contents=prompt)
                return response.text or ""
            except Exception as exc:  # rate limits / 5xx
                message = str(exc)
                last_error = message.split("{")[0].strip()[:160]
                hint = _RETRY_IN.search(message)
                time.sleep(float(hint.group(1)) + 1 if hint else delay)
                delay = min(delay * 2, 60.0)
        raise RuntimeError(f"Gemini call failed after {max_attempts} attempts: {last_error}")

    return _call


def load_corpus_pages(upload_dir: str, cache_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Extract pages from every supported upload, caching the result as JSON.

    OCR on scanned PDFs is slow, so the extracted pages are cached and reused by
    both the QA generator and the model comparison.
    """
    if cache_path and Path(cache_path).exists():
        return json.loads(Path(cache_path).read_text(encoding="utf-8"))

    from src.api.dependencies import SUPPORTED_EXTENSIONS
    from src.ingestion.document_extractor import extract_pages_from_document
    from src.ingestion.ocr_engine import OcrEngine

    ocr_engine = OcrEngine()
    pages: List[Dict[str, Any]] = []
    for path in sorted(Path(upload_dir).iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file() or path.name.startswith(".") or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        doc_name = nfc(path.name)
        for page in extract_pages_from_document(str(path), ocr_engine=ocr_engine):
            if page.get("text", "").strip():
                pages.append({
                    "doc_name": doc_name,
                    "page_number": int(page.get("page_number", 1)),
                    "text": page["text"],
                    "is_scanned": bool(page.get("is_scanned", False)),
                })

    if cache_path:
        Path(cache_path).parent.mkdir(parents=True, exist_ok=True)
        Path(cache_path).write_text(json.dumps(pages, ensure_ascii=False), encoding="utf-8")
    return pages


def generate_question_for_page(page: Dict[str, Any], llm: LLMFn, max_chars: int = 3500) -> Optional[Dict[str, Any]]:
    """Ask the LLM for one grounded question about a page; None when skipped/invalid."""
    prompt = QA_PROMPT.format(
        doc_name=page["doc_name"],
        page=page["page_number"],
        text=page["text"][:max_chars],
    )
    parsed = parse_json_object(llm(prompt))
    if not parsed or parsed.get("skip"):
        return None
    question = str(parsed.get("question") or "").strip()
    if len(question) < 10:
        return None
    return {
        "question": question,
        "expected_doc": page["doc_name"],
        "expected_pages": [page["page_number"]],
        "ground_truth_answer": str(parsed.get("answer") or "").strip(),
        "type": str(parsed.get("type") or "factual"),
        "should_abstain": False,
        "source_excerpt": page["text"][:300],
    }


def judge_passages(question: str, passages: Sequence[str], llm: LLMFn, max_chars: int = 1200) -> List[Optional[int]]:
    """Grade passages 0/1/2 for the question. Returns None for ungraded passages."""
    if not passages:
        return []
    body = "\n\n".join(f"[P{i + 1}]\n{text[:max_chars]}" for i, text in enumerate(passages))
    parsed = parse_json_object(llm(JUDGE_PROMPT.format(question=question, passages=body))) or {}
    grades_raw = parsed.get("grades", parsed)
    grades: List[Optional[int]] = []
    for i in range(len(passages)):
        value = grades_raw.get(f"P{i + 1}") if isinstance(grades_raw, dict) else None
        try:
            grades.append(max(0, min(2, int(value))))
        except (TypeError, ValueError):
            grades.append(None)
    return grades


def graded_ndcg(grades: Sequence[Optional[int]], ideal_pool: Sequence[Optional[int]], k: int) -> float:
    """nDCG@k with graded relevance; the ideal ranking comes from the pooled grades."""
    def dcg(values: Sequence[int]) -> float:
        return sum((2 ** g - 1) / math.log2(rank + 2) for rank, g in enumerate(values[:k]))

    actual = [g or 0 for g in grades]
    ideal = sorted((g or 0 for g in ideal_pool), reverse=True)
    ideal_dcg = dcg(ideal)
    return dcg(actual) / ideal_dcg if ideal_dcg > 0 else 0.0


def shuffled_pool(texts_by_config: Dict[str, List[str]], seed: int) -> List[str]:
    """Deduplicate passages across configs and shuffle them deterministically."""
    pool: List[str] = []
    seen = set()
    for texts in texts_by_config.values():
        for text in texts:
            key = text.strip()
            if key and key not in seen:
                seen.add(key)
                pool.append(key)
    random.Random(seed).shuffle(pool)
    return pool
