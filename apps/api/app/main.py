import os
import json
from time import perf_counter
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

import psycopg
from typing import Literal
from psycopg.rows import dict_row
from confluent_kafka import Producer
from fastapi import FastAPI, HTTPException, Query
from prometheus_fastapi_instrumentator import Instrumentator
from apps.api.app.metrics import (
    TRACES_INGESTED, INGESTION_ERRORS, INGESTION_LATENCY
)
from pydantic import BaseModel, Field


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://agentscope:agentscope_dev@127.0.0.1:5433/agentscope",
)

producer = Producer({
    "bootstrap.servers": os.getenv(
        "KAFKA_BOOTSTRAP_SERVERS",
        "127.0.0.1:9092",
    ),
    "enable.idempotence": True,
    "acks": "all",
})


class TraceEvent(BaseModel):
    run_id: UUID
    span_id: UUID
    parent_span_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    span_type: str = Field(pattern="^(agent|llm|tool)$")
    status: str = Field(pattern="^(ok|error)$")
    timestamp: datetime
    metadata: dict = Field(default_factory=dict)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    producer.flush(timeout=10)


app = FastAPI(
    title="AgentScope API",
    description="Distributed observability platform for AI agents",
    version="0.1.0",
    lifespan=lifespan,
)


Instrumentator().instrument(app).expose(app, endpoint="/metrics")

@app.get("/")
def root():
    return {
        "message": "AgentScope API is running",
        "version": "0.1.0",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/v1/traces", status_code=202)
def ingest_trace(event: TraceEvent):
    started = perf_counter()
    try:
        producer.produce(
            topic="agent-traces",
            key=str(event.run_id),
            value=json.dumps(
                event.model_dump(mode="json")
            ).encode("utf-8"),
        )

        remaining = producer.flush(timeout=10)

        if remaining:
            raise RuntimeError("Kafka delivery timed out")

        TRACES_INGESTED.inc()
        return {
            "message": "Trace accepted",
            "span_id": str(event.span_id),
        }

    except Exception as exc:
        INGESTION_ERRORS.inc()
        raise HTTPException(
            status_code=503,
            detail="Kafka ingestion unavailable",
        ) from exc

    finally:
        INGESTION_LATENCY.observe(perf_counter() - started)


@app.get("/v1/runs")
def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    status: Literal["ok", "error"] | None = None,
):
    try:
        with psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row,
        ) as conn:
            rows = conn.execute(
                """
                SELECT
                    run_id,
                    COUNT(*) AS span_count,
                    MIN(timestamp) AS started_at,
                    MAX(timestamp) AS last_event_at,
                    COUNT(*) FILTER (
    WHERE status = 'error'
) AS error_count,

COALESCE(
    SUM(
        CASE
            WHEN span_type = 'llm'
             AND jsonb_typeof(metadata->'input_tokens') = 'number'
            THEN (metadata->>'input_tokens')::numeric
            ELSE 0
        END
    ),
    0
)::bigint AS input_tokens,

COALESCE(
    SUM(
        CASE
            WHEN span_type = 'llm'
             AND jsonb_typeof(metadata->'output_tokens') = 'number'
            THEN (metadata->>'output_tokens')::numeric
            ELSE 0
        END
    ),
    0
)::bigint AS output_tokens,

COALESCE(
    SUM(
        CASE
            WHEN span_type = 'llm'
             AND jsonb_typeof(metadata->'input_tokens') = 'number'
             AND jsonb_typeof(metadata->'output_tokens') = 'number'
             AND jsonb_typeof(metadata->'input_cost_per_million') = 'number'
             AND jsonb_typeof(metadata->'output_cost_per_million') = 'number'
            THEN (
                (metadata->>'input_tokens')::numeric
                * (metadata->>'input_cost_per_million')::numeric
                +
                (metadata->>'output_tokens')::numeric
                * (metadata->>'output_cost_per_million')::numeric
            ) / 1000000
            ELSE 0
        END
    ),
    0
) AS estimated_cost_usd
                FROM spans
GROUP BY run_id
HAVING (
    %s::text IS NULL
    OR (
        %s = 'error'
        AND COUNT(*) FILTER (WHERE status = 'error') > 0
    )
    OR (
        %s = 'ok'
        AND COUNT(*) FILTER (WHERE status = 'error') = 0
    )
)
ORDER BY last_event_at DESC
LIMIT %s
                """,
                (status, status, status, limit),
            ).fetchall()

    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from exc

    return {
        "count": len(rows),
        "runs": [
            {
                **row,
                "status": (
                    "error" if row["error_count"] > 0 else "ok"
                ),
            }
            for row in rows
        ],
    }


@app.get("/v1/traces/{run_id}")
def get_trace(run_id: UUID):
    try:
        with psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row,
        ) as conn:
            rows = conn.execute("""
    SELECT
        span_id,
        run_id,
        parent_span_id,
        name,
        span_type,
        status,
        timestamp,
        metadata,
        created_at
    FROM spans
    WHERE run_id = %s
    ORDER BY timestamp ASC, span_id ASC
""", (run_id,)).fetchall()

    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from exc

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="Trace not found",
        )

    return {
        "run_id": str(run_id),
        "span_count": len(rows),
        "spans": rows,
    }


@app.get("/v1/runs/{run_id}/diagnosis")
def get_run_diagnosis(run_id: UUID):
    from .diagnosis import diagnose_run

    trace = get_trace(run_id)
    result = diagnose_run(trace["spans"])

    return {
        "run_id": str(run_id),
        **result,
    }
