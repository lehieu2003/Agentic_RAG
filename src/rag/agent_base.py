"""Shared low-level helpers for the Agentic RAG engine.

Contains text normalization and provider-agnostic LLM invocation so that
the chit-chat, query-processing, and graph-node mixins can share them.
"""

import logging
import time
import unicodedata

logger = logging.getLogger(__name__)


class AgentBaseMixin:
    """Text normalization and LLM invocation helpers shared by all agent mixins."""

    def _remove_accents(self, text: str) -> str:
        """Convert accented Vietnamese text to unaccented ASCII equivalent."""
        s = text.replace("đ", "d").replace("Đ", "D")
        nfkd = unicodedata.normalize("NFKD", s)
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    def _call_llm(self, prompt: str) -> str:
        """Execute LLM generation, logging the round-trip duration."""
        start = time.perf_counter()
        result = self._call_llm_impl(prompt)
        logger.info("llm call (%s) took %.2fs", self.provider, time.perf_counter() - start)
        return result

    def _call_llm_impl(self, prompt: str) -> str:
        """Provider dispatch with automatic model fallback for high availability."""
        if self.llm_client is None:
            return ""
        if self.provider == "gemini":
            candidate_models = [self.model_name]
            for fb in ["gemini-flash-lite-latest", "gemini-3.1-flash-lite"]:
                if fb not in candidate_models:
                    candidate_models.append(fb)
            for m in candidate_models:
                try:
                    response = self.llm_client.models.generate_content(
                        model=m,
                        contents=prompt
                    )
                    text = response.text or ""
                    if text:
                        return text
                except Exception as e:
                    logger.debug("Gemini candidate model '%s' failed: %s", m, e)
                    continue
            logger.warning("All Gemini candidate models %s failed: returning empty response", candidate_models)
            return ""
        elif self.provider == "openai":
            try:
                response = self.llm_client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                logger.warning("OpenAI call failed: returning empty response: %s", e)
                return ""
        elif self.provider == "mock" or (hasattr(self.llm_client, "generate") and callable(self.llm_client.generate)):
            try:
                res = self.llm_client.generate(prompt)
                return str(res) if res is not None else ""
            except Exception as e:
                logger.warning(f"Mock LLM call failed: {e}")
                return ""
        return ""
