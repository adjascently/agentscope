
import logging
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Iterator
from uuid import UUID, uuid4

import requests

logger = logging.getLogger("agentscope")


class AgentScope:
    def __init__(self, endpoint: str = "http://127.0.0.1:8000"):
        self.endpoint = endpoint.rstrip("/")

        self._run_id: ContextVar[UUID | None] = ContextVar(
            "agentscope_run_id", default=None
        )
        self._current_span_id: ContextVar[UUID | None] = ContextVar(
            "agentscope_current_span_id", default=None
        )

    @property
    def run_id(self) -> UUID | None:
        return self._run_id.get()

    @contextmanager
    def trace(self, name: str) -> Iterator[UUID]:
        if self.run_id is not None:
            raise RuntimeError("A trace is already active")

        run_id = uuid4()
        token = self._run_id.set(run_id)

        try:
            with self.span(
                name,
                span_type="agent",
                metadata={"agent_name": name},
            ):
                yield run_id
        finally:
            self._run_id.reset(token)

    @contextmanager
    def span(
        self,
        name: str,
        span_type: str = "tool",
        metadata: dict | None = None,
    ) -> Iterator[None]:
        run_id = self.run_id

        if run_id is None:
            raise RuntimeError("Start a trace before creating spans")

        if span_type not in {"agent", "llm", "tool"}:
            raise ValueError("span_type must be agent, llm, or tool")

        span_id = uuid4()

        # The currently active span becomes this span's parent.
        parent_span_id = self._current_span_id.get()

        # Set this span as the active parent for nested operations.
        token = self._current_span_id.set(span_id)

        started_at = datetime.now(timezone.utc)
        start = time.perf_counter()

        status = "ok"
        details = dict(metadata or {})

        try:
            yield

        except Exception as exc:
            status = "error"
            details["error_message"] = str(exc)
            raise

        finally:
            # Restore the previous active span.
            self._current_span_id.reset(token)

            details["latency_ms"] = round(
                (time.perf_counter() - start) * 1000,
                2,
            )

            event = {
                "run_id": str(run_id),
                "span_id": str(span_id),
                "parent_span_id": (
                    str(parent_span_id)
                    if parent_span_id is not None
                    else None
                ),
                "name": name,
                "span_type": span_type,
                "status": status,
                "timestamp": started_at.isoformat(),
                "metadata": details,
            }

            try:
                response = requests.post(
                    f"{self.endpoint}/v1/traces",
                    json=event,
                    timeout=5,
                )
                response.raise_for_status()

            except requests.RequestException:
                logger.exception(
                    "Failed to publish span %s",
                    span_id,
                )
