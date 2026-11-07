"""Chat use-case: turn a user question into a persisted, cited answer.

Orchestration extracted from the API router so session management, history
loading, agent invocation, and message persistence live in one testable
place, independent of the web framework.
"""

from typing import Any, Optional

from src.domain.exceptions import RetrievalError
from src.models import QAResponse
from src.storage.session_store import SessionStore

# Number of previous messages loaded as conversational context for the agent.
HISTORY_MESSAGE_LIMIT = 10


class ChatService:
    """Runs one Q&A turn: session resolution, agent invocation, persistence."""

    def __init__(self, agent: Any, session_store: SessionStore, default_top_k: int) -> None:
        self._agent = agent
        self._session_store = session_store
        self._default_top_k = default_top_k

    def answer(
        self,
        question: str,
        top_k: Optional[int] = None,
        session_id: Optional[str] = None,
    ) -> QAResponse:
        """Answer ``question`` within the conversation identified by ``session_id``.

        Creates the session on first contact, feeds the recent history to the
        agent, and persists both sides of the turn. Raises
        :class:`RetrievalError` when the agent pipeline fails.
        """
        resolved_session_id = self._resolve_session(question, session_id)

        # 2. Load recent messages so the agent can contextualize the question
        recent_messages = self._session_store.get_recent_messages(
            resolved_session_id, limit=HISTORY_MESSAGE_LIMIT
        )

        # 3. Invoke the agentic pipeline
        try:
            response = self._agent.answer(
                question,
                top_k=top_k or self._default_top_k,
                history=recent_messages,
            )
        except Exception as e:
            raise RetrievalError(f"Retrieval failure: {str(e)}") from e

        # 4. Persist user and assistant messages
        self._persist_turn(resolved_session_id, question, response)

        return response.model_copy(update={"session_id": resolved_session_id})

    def answer_stream(
        self,
        question: str,
        top_k: Optional[int] = None,
        session_id: Optional[str] = None,
    ):
        """Yield streaming events for one Q&A turn (SSE payload source).

        Events, in order: ``{"type": "session"}`` once the conversation is
        resolved, ``{"type": "step"}`` per reasoning step as nodes complete,
        then ``{"type": "answer"}`` with the full :class:`QAResponse` and
        ``{"type": "done"}`` — or a single ``{"type": "error"}``. Messages are
        persisted exactly like :meth:`answer` once the answer is available.
        """
        resolved_session_id = self._resolve_session(question, session_id)
        yield {"type": "session", "session_id": resolved_session_id}

        recent_messages = self._session_store.get_recent_messages(
            resolved_session_id, limit=HISTORY_MESSAGE_LIMIT
        )

        final_response: Optional[QAResponse] = None
        try:
            for kind, payload in self._agent.stream_answer(
                question,
                top_k=top_k or self._default_top_k,
                history=recent_messages,
            ):
                if kind == "step":
                    yield {"type": "step", "step": payload}
                else:
                    final_response = payload
        except Exception as e:
            yield {"type": "error", "detail": f"Retrieval failure: {str(e)}"}
            return

        if final_response is None:
            yield {"type": "error", "detail": "Retrieval failure: the pipeline returned no result."}
            return

        try:
            self._persist_turn(resolved_session_id, question, final_response)
        except Exception as e:
            yield {"type": "error", "detail": f"Failed to persist the conversation: {str(e)}"}
            return

        yield {
            "type": "answer",
            "response": final_response.model_copy(update={"session_id": resolved_session_id}),
        }
        yield {"type": "done", "session_id": resolved_session_id}

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _resolve_session(self, question: str, session_id: Optional[str]) -> str:
        """Return the existing or newly created conversation id."""
        session_title = question[:40].strip() or "Cuộc trò chuyện mới"
        req_session_id = (session_id or "").strip()
        if req_session_id:
            existing = self._session_store.get_session(req_session_id)
            if existing:
                return req_session_id
            return self._session_store.create_session(
                session_id=req_session_id, title=session_title
            )
        return self._session_store.create_session(title=session_title)

    def _persist_turn(self, session_id: str, question: str, response: QAResponse) -> None:
        """Store both sides of the completed turn."""
        self._session_store.add_message(
            session_id=session_id,
            role="user",
            content=question,
        )
        self._session_store.add_message(
            session_id=session_id,
            role="assistant",
            content=response.answer,
            standalone_question=response.standalone_question,
            citations=response.citations,
            reasoning_steps=response.reasoning_steps,
        )


__all__ = ["ChatService", "HISTORY_MESSAGE_LIMIT"]
