import os
import json
import logging
import signal
from time import perf_counter

from prometheus_client import start_http_server
from apps.api.app.metrics import (
    CONSUMER_PROCESSED,
    CONSUMER_ERRORS,
    CONSUMER_LATENCY,
)

import psycopg
from confluent_kafka import Consumer, KafkaError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

logger = logging.getLogger("agentscope.consumer")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://agentscope:agentscope_dev@127.0.0.1:5433/agentscope",
)

consumer = Consumer({
   "bootstrap.servers": os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS",
    "127.0.0.1:9092",
),
    "group.id": "agentscope-postgres-writer",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,
})

running = True


def shutdown(signum, frame):
    global running
    running = False


signal.signal(signal.SIGINT, shutdown)
signal.signal(signal.SIGTERM, shutdown)


def save_trace(conn, event):
    with conn.transaction():
        conn.execute("""
            INSERT INTO spans (
                span_id,
                run_id,
                parent_span_id,
                name,
                span_type,
                status,
                timestamp,
                metadata
            )
            VALUES (
                %(span_id)s,
                %(run_id)s,
                %(parent_span_id)s,
                %(name)s,
                %(span_type)s,
                %(status)s,
                %(timestamp)s,
                %(metadata)s::jsonb
            )
            ON CONFLICT (span_id) DO NOTHING
        """, {
            "span_id": event["span_id"],
            "run_id": event["run_id"],
            "parent_span_id": event.get("parent_span_id"),
            "name": event["name"],
            "span_type": event["span_type"],
            "status": event["status"],
            "timestamp": event["timestamp"],
            "metadata": json.dumps(event["metadata"]),
        })


def main():
    start_http_server(8002, addr="0.0.0.0")
    logger.info("Starting AgentScope Kafka consumer")

    try:
        with psycopg.connect(
            DATABASE_URL,
            autocommit=True,
        ) as conn:

            consumer.subscribe(["agent-traces"])

            while running:
                message = consumer.poll(1.0)

                if message is None:
                    continue

                if message.error():
                    if (
                        message.error().code()
                        == KafkaError._PARTITION_EOF
                    ):
                        continue

                    logger.error(
                        "Kafka error: %s",
                        message.error(),
                    )
                    continue

                started = perf_counter()
                try:
                    event = json.loads(message.value())

                    save_trace(conn, event)

                    consumer.commit(
                        message=message,
                        asynchronous=False,
                    )

                    CONSUMER_PROCESSED.inc()
                    logger.info(
                        "Saved trace: %s (%s)",
                        event["name"],
                        event["span_id"],
                    )

                except Exception:
                    CONSUMER_ERRORS.inc()
                    logger.exception(
                        "Failed to process trace; "
                        "stopping without committing "
                        "the failed message"
                    )
                    break

                finally:
                    CONSUMER_LATENCY.observe(perf_counter() - started)

    finally:
        consumer.close()
        logger.info("Consumer stopped")


if __name__ == "__main__":
    main()
