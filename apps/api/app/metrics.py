from prometheus_client import Counter, Histogram

TRACES_INGESTED = Counter(
    "agentscope_traces_ingested_total",
    "Number of traces successfully accepted by Kafka",
)

INGESTION_ERRORS = Counter(
    "agentscope_ingestion_errors_total",
    "Number of trace ingestion failures",
)

INGESTION_LATENCY = Histogram(
    "agentscope_ingestion_duration_seconds",
    "Time spent publishing a trace to Kafka",
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)

CONSUMER_PROCESSED = Counter(
    "agentscope_consumer_processed_total",
    "Number of Kafka messages successfully processed",
)

CONSUMER_ERRORS = Counter(
    "agentscope_consumer_errors_total",
    "Number of Kafka message processing errors",
)

CONSUMER_LATENCY = Histogram(
    "agentscope_consumer_processing_seconds",
    "Time taken to process and commit a Kafka message",
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)
