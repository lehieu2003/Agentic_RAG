"""OCR Engine implementation using RapidOCR."""

from rapidocr_onnxruntime import RapidOCR


class OcrEngine:
    """Wrapper for optical character recognition on scanned pages and images."""

    def __init__(self):
        self._engine = RapidOCR()

    def extract_text_from_image(self, image_bytes: bytes) -> str:
        """Extract text from raw image bytes.

        Args:
            image_bytes: PNG or JPEG encoded image bytes.

        Returns:
            Extracted text string.
        """
        if not image_bytes:
            return ""

        try:
            # RapidOCR accepts bytes, ndarray, or file path
            result, _ = self._engine(image_bytes)
            if not result:
                return ""

            # result format: [[box, text, score], ...]
            extracted_lines = [item[1] for item in result if len(item) > 1 and item[1]]
            return "\n".join(extracted_lines)
        except Exception:
            return ""

