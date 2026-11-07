"""In-memory registry tracking background ingestion jobs.

Jobs live in process memory by design: the heavy artifacts (stored file,
vectors, BM25 entries) are durable once a job succeeds, so only the
*progress view* is lost on restart. Registries are per-worker, which
matches the single-process deployment (see docker-compose).
"""

import threading
from collections import OrderedDict
from datetime import datetime, timezone

from src.models import IngestionJobResponse, IngestionJobStatus

# Finished jobs kept for polling before eviction; bounded to avoid growth.
MAX_RETAINED_JOBS = 200


class IngestionJobStore:
    """Thread-safe store of :class:`IngestionJobResponse` records."""

    def __init__(self, max_retained: int = MAX_RETAINED_JOBS) -> None:
        self._jobs: "OrderedDict[str, IngestionJobResponse]" = OrderedDict()
        self._lock = threading.Lock()
        self._max_retained = max_retained

    def create(self, filename: str, job_id: str) -> IngestionJobResponse:
        """Register a new job in the ``queued`` state and return its snapshot."""
        job = IngestionJobResponse(
            job_id=job_id,
            filename=filename,
            status=IngestionJobStatus.QUEUED,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        with self._lock:
            self._jobs[job_id] = job
            self._prune_locked()
        return job.model_copy()

    def get(self, job_id: str) -> IngestionJobResponse | None:
        """Return a snapshot of the job, or ``None`` when unknown."""
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy() if job else None

    def mark_running(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None and job.status == IngestionJobStatus.QUEUED:
                self._jobs[job_id] = job.model_copy(
                    update={
                        "status": IngestionJobStatus.RUNNING,
                        "started_at": datetime.now(timezone.utc).isoformat(),
                    }
                )

    def mark_finished(
        self,
        job_id: str,
        status: IngestionJobStatus,
        result=None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            self._jobs[job_id] = job.model_copy(
                update={
                    "status": status,
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "result": result,
                    "error": error,
                }
            )

    def _prune_locked(self) -> None:
        """Evict oldest finished jobs once the retention bound is exceeded."""
        while len(self._jobs) > self._max_retained:
            for job_id, job in self._jobs.items():
                if job.status in (
                    IngestionJobStatus.SUCCESS,
                    IngestionJobStatus.ALREADY_EXISTS,
                    IngestionJobStatus.FAILED,
                ):
                    del self._jobs[job_id]
                    break
            else:
                break  # only unfinished jobs remain; keep them


__all__ = ["IngestionJobStore", "MAX_RETAINED_JOBS"]
