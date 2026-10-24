import argparse
import json
import random
import time
import urllib.request
from datetime import datetime, timezone
from uuid import uuid4

DEFAULT_API = "http://127.0.0.1:8001"
WORKFLOWS = {
    "Research Assistant": [
        ("agent.plan", "agent"),
        ("openai.chat.completions", "llm"),
        ("tools.web_search", "tool"),
        ("openai.chat.completions", "llm"),
        ("agent.final_response", "agent"),
    ],
    "Code Review Agent": [
        ("agent.plan", "agent"),
        ("tools.read_repository", "tool"),
        ("openai.chat.completions", "llm"),
        ("tools.run_tests", "tool"),
        ("agent.final_response", "agent"),
    ],
    "Customer Support Agent": [
        ("agent.plan", "agent"),
        ("tools.search_knowledge_base", "tool"),
        ("openai.chat.completions", "llm"),
        ("agent.final_response", "agent"),
    ],
    "Data Analysis Agent": [
        ("agent.plan", "agent"),
        ("tools.query_database", "tool"),
        ("tools.transform_data", "tool"),
        ("openai.chat.completions", "llm"),
        ("agent.final_response", "agent"),
    ],
    "Document Processing Agent": [
        ("agent.plan", "agent"),
        ("tools.extract_text", "tool"),
        ("openai.chat.completions", "llm"),
        ("agent.final_response", "agent"),
    ],
}

FAILURES = [
    ("quota_exhausted", "insufficient_quota"),
    ("rate_limited", "rate_limit_exceeded"),
    ("authentication_failed", "invalid_api_key"),
    ("timeout", "Request timed out"),
    ("connection_failed", "Connection refused"),
]


def publish(api, event):
    request = urllib.request.Request(
        f"{api}/v1/traces",
        data=json.dumps(event).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status != 202:
            raise RuntimeError(f"Unexpected status: {response.status}")


def run_workflow(api, rng, index):
    agent_name = rng.choice(list(WORKFLOWS))
    steps = WORKFLOWS[agent_name]
    run_id = str(uuid4())
    failed = rng.random() < 0.3
    failure_step = rng.choice(
        [i for i, (_, kind) in enumerate(steps) if kind in ("llm", "tool")]
    ) if failed else None
    failure = rng.choice(FAILURES) if failed else None

    base_time = datetime.now(timezone.utc)
    parent_id = str(uuid4())

    for step_index, (name, kind) in enumerate(steps):
        span_id = str(uuid4())
        is_failure = step_index == failure_step
        latency_ms = rng.randint(80, 2400)

        metadata = {
            "agent_name": agent_name,
            "environment": "synthetic-demo",
            "synthetic": True,
            "step_number": step_index + 1,
            "latency_ms": latency_ms,
        }

        if kind == "llm":
            input_tokens = rng.randint(100, 1800)
            output_tokens = rng.randint(40, 700)
            metadata.update({
                "model": rng.choice(["gpt-4o", "gpt-4o-mini"]),
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            })

        if is_failure:
            code, message = failure
            metadata["error_code"] = code if code != "timeout" else "timeout"
            metadata["error_message"] = message

        event = {
            "run_id": run_id,
            "span_id": span_id,
            "parent_span_id": parent_id if step_index > 0 else None,
            "name": name,
            "span_type": kind,
            "status": "error" if is_failure else "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata,
        }

        publish(api, event)

        if step_index == 0:
            parent_id = span_id

    return run_id, agent_name, failed, len(steps)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--interval", type=float, default=0.3)
    parser.add_argument("--api", default=DEFAULT_API)
    args = parser.parse_args()

    if args.count < 1 or args.interval < 0:
        parser.error("--count must be positive and --interval nonnegative")

    rng = random.Random()
    print(f"Publishing {args.count} synthetic runs to {args.api}")

    for i in range(args.count):
        run_id, agent, failed, spans = run_workflow(args.api, rng, i)
        status = "ERROR" if failed else "OK"
        print(f"[{i + 1}/{args.count}] {agent} | {status} | {spans} spans | {run_id}", flush=True)
        if i + 1 < args.count:
            time.sleep(args.interval)

    print("All runs submitted to ingestion API.")
    print("Kafka consumer may need a few seconds to persist the traces.")


if __name__ == "__main__":
    main()
