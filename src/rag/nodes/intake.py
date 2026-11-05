"""Graph nodes 0-2: query contextualization, intent routing, and query expansion."""

import re
from typing import Any, Dict

from langgraph.graph import END

from src.rag.prompt import CONTEXTUALIZE_QUERY_PROMPT
from src.rag.state import AgentState


class IntakeNodesMixin:
    """Nodes that normalize the incoming question before any retrieval happens."""

    def _node_contextualize_query(self, state: AgentState) -> Dict[str, Any]:
        """Node 0: Contextualize user question with conversation history into standalone query."""
        raw_question = state.get("question", "").strip()
        history = state.get("history") or []
        steps = list(state.get("reasoning_steps", []))

        # Fast path: bypass LLM if history is empty or if query is chitchat
        if not history or self._detect_chitchat(raw_question):
            return {
                "standalone_question": raw_question,
                "reasoning_steps": steps,
            }

        # Build formatted history lines
        history_lines = []
        for msg in history:
            role = msg.get("role", "user")
            label = "Người dùng" if role == "user" else "Trợ lý"
            content = msg.get("content", "").strip()
            history_lines.append(f"{label}: {content}")
        history_text = "\n".join(history_lines)

        prompt = CONTEXTUALIZE_QUERY_PROMPT.format(
            history=history_text,
            question=raw_question,
        )

        try:
            standalone_q = self._call_llm(prompt).strip()
            if standalone_q:
                standalone_q = re.sub(r'^["\']|["\']$', '', standalone_q).strip()
            if not standalone_q:
                standalone_q = raw_question
        except Exception as e:
            logger.warning(f"Error during query contextualization: {e}. Falling back to raw query.")
            standalone_q = raw_question

        steps.append(f"0. contextualize: Đã chuẩn hóa câu hỏi theo ngữ cảnh: {standalone_q}")
        return {
            "standalone_question": standalone_q,
            "reasoning_steps": steps,
        }

    def _node_router(self, state: AgentState) -> Dict[str, Any]:
        """Node 1: Smart Chit-chat & Intent Extractor."""
        target_q = state.get("standalone_question", state.get("question", "")).strip()

        # 1. Pure chitchat check on full query
        reply = self._detect_chitchat(target_q)
        if reply:
            return {
                "clean_question": target_q,
                "is_chitchat": True,
                "chitchat_reply": reply,
                "answer": reply,
                "abstained": False,
                "citations": [],
                "candidate_chunks": [],
                "reranked_chunks": [],
                "all_queries": [target_q],
                "reasoning_steps": list(state.get("reasoning_steps", [])) + ["1. router: Nhận diện câu hỏi là lời chào hỏi / giao tiếp thông thường (Chit-chat Router)"]
            }

        # 2. Greeting prefix stripping for mixed-intent queries
        clean_q = self.GREETING_PREFIX_PATTERN.sub("", target_q).strip()
        if not clean_q:
            clean_q = target_q

        reply_stripped = self._detect_chitchat(clean_q)
        if reply_stripped:
            return {
                "clean_question": clean_q,
                "is_chitchat": True,
                "chitchat_reply": reply_stripped,
                "answer": reply_stripped,
                "abstained": False,
                "citations": [],
                "candidate_chunks": [],
                "reranked_chunks": [],
                "all_queries": [clean_q],
                "reasoning_steps": list(state.get("reasoning_steps", [])) + ["1. router: Nhận diện câu hỏi là lời chào hỏi / giao tiếp thông thường (Fast-path Router)"]
            }

        # 3. Tier 2: LLM Intent Classifier fallback for novel / conversational phrasing
        llm_reply = self._classify_intent_with_llm(clean_q)
        if llm_reply:
            return {
                "clean_question": clean_q,
                "is_chitchat": True,
                "chitchat_reply": llm_reply,
                "answer": llm_reply,
                "abstained": False,
                "citations": [],
                "candidate_chunks": [],
                "reranked_chunks": [],
                "all_queries": [clean_q],
                "reasoning_steps": list(state.get("reasoning_steps", [])) + ["1. router: Mô hình LLM nhận diện câu hỏi là hội thoại thông thường / hỏi năng lực trợ lý (LLM Intent Router)"]
            }

        steps = list(state.get("reasoning_steps", []))
        steps.append(f"1. router: Đã chuẩn hóa câu hỏi: '{clean_q}' (loại bỏ lời chào hỏi nếu có)")
        return {
            "clean_question": clean_q,
            "is_chitchat": False,
            "reasoning_steps": steps
        }

    def _route_after_router(self, state: AgentState) -> str:
        """Route to END if pure chitchat, else proceed to 2_expand_query."""
        if state.get("is_chitchat"):
            return END
        return "2_expand_query"

    def _node_expand_query(self, state: AgentState) -> Dict[str, Any]:
        """Node 2: Multilingual / OCR query generator."""
        clean_q = state.get("clean_question", state["question"])
        expanded = self.expand_query(clean_q)
        if not expanded:
            expanded = [clean_q]
        steps = list(state.get("reasoning_steps", []))
        steps.append(f"2. expand_query: Mở rộng truy vấn thành {len(expanded)} biến thể: {expanded}")
        return {
            "queries": expanded,
            "all_queries": list(expanded),
            "reasoning_steps": steps
        }
