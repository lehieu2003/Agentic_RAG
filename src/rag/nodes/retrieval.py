"""Graph nodes 3-4: multi-query hybrid retrieval and cross-encoder reranking."""

from typing import Any, Dict

from src.rag.state import AgentState


class RetrievalNodesMixin:
    """Nodes that gather candidate chunks and rank them for the grader."""

    def _node_hybrid_retrieve(self, state: AgentState) -> Dict[str, Any]:
        """Node 3: Multi-query retrieval merging candidates via RRF."""
        queries_to_run = state.get("queries") or [state.get("clean_question", state["question"])]
        top_k = state.get("top_k", 5)
        new_chunks = self.multi_query_retrieve(queries_to_run, top_k=top_k)
        existing = state.get("candidate_chunks", [])
        merged = self._merge_chunks(existing + new_chunks, top_k=top_k)
        candidate_pool = merged[:self.candidate_pool_size]
        max_score = max((c.score for c in candidate_pool), default=0.0)

        steps = list(state.get("reasoning_steps", []))
        steps.append(
            f"3. hybrid_retrieve: Truy xuất được {len(candidate_pool)} đoạn tài liệu ứng viên "
            f"từ {len(queries_to_run)} truy vấn (điểm cao nhất: {max_score:.2f})"
        )
        return {
            "candidate_chunks": candidate_pool,
            "max_score": max_score,
            "reasoning_steps": steps
        }

    def _node_rerank(self, state: AgentState) -> Dict[str, Any]:
        """Node 4: Local Cross-Encoder Reranking."""
        clean_q = state.get("clean_question", state["question"])
        candidates = state.get("candidate_chunks", [])
        top_k = state.get("top_k", 5)
        # For complex multi-part queries, expand effective context according to configuration
        target_k = max(top_k, self.complex_query_top_k) if len(clean_q) > self.complex_query_threshold else top_k
        steps = list(state.get("reasoning_steps", []))

        if self.reranker is not None and candidates:
            try:
                reranked = self.reranker.rerank(clean_q, candidates, top_k=target_k)
            except Exception as e:
                steps.append(f"4. rerank: Cảnh báo lỗi reranker ({str(e)}), dùng kết quả truy xuất gốc.")
                reranked = candidates[:target_k]
        else:
            reranked = candidates[:target_k]

        # Guard: Preserve top candidates from hybrid search if absent from reranked set
        reranked_keys = {self._get_chunk_key(r.chunk) for r in reranked}
        for top_candidate in candidates[:self.top_preservation_k]:
            key = self._get_chunk_key(top_candidate.chunk)
            if key not in reranked_keys:
                reranked.append(top_candidate)
                reranked_keys.add(key)

        steps.append(f"4. rerank: Đã đánh giá và xếp hạng lại {len(reranked)} đoạn tài liệu phù hợp nhất")
        return {
            "reranked_chunks": reranked,
            "reasoning_steps": steps
        }
