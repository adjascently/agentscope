
import json
import random
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from uuid import uuid4


API_URL = "http://127.0.0.1:8000/v1/traces"

AGENT_WORKFLOWS = [
    {
        "name": "Research Assistant",
        "steps": [
            ("agent.plan", "agent", "ok"),
            ("openai.chat.completions", "llm", "ok"),
            ("tools.web_search", "tool", "ok"),
            ("openai.chat.completions", "llm", "ok"),
            ("agent.final_response", "agent", "ok"),
        ],
    },
    {
        "name": "Code Review Agent",
        "steps": [
            ("agent.plan", "agent", "ok"),
            ("tools.read_repository", "tool", "ok"),
            ("openai.chat.completions", "llm", "ok"),
            ("tools.run_tests", "tool", "error"),
            ("agent.handle_error", "agent", "ok"),
            ("agent.final_response", "agent", "ok"),
        ],
    },
    {
        "name": "Customer Support Agent",
        "steps": [
            ("agent.plan", "agent", "ok"),
            ("tools.search_knowledge_base", "tool", "ok"),
            ("openai.chat.completions", "llm", "ok"),
            ("agent.final_response", "agent", "ok"),
        ],
    },
]


def send_trace(event):
    payload = json.dumps(event).encode("utf-8")

    request = urllib.request.Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status != 202:
            raise RuntimeError(
                f"Unexpected API status: {response.status}"
            )


def generate_workflow(workflow, index):
    run_id = str(uuid4())
    start_time = datetime.now(timezone.utc) - timedelta(
        minutes=index * 5
    )

    print(f"\nGenerating: {workflow['name']}")
    print(f"Run ID: {run_id}")

    for step_number, (name, span_type, status) in enumerate(
        workflow["steps"], start=1
    ):
        latency_ms = random.randint(100, 1800)

        metadata = {
            "agent_name": workflow["name"],
            "step_number": step_number,
            "latency_ms": latency_ms,
            "environment": "demo",
        }

        if span_type == "llm":
            metadata.update({
                "model": "gpt-4o",
                "tokens": random.randint(100, 1200),
            })

        if status == "error":
            metadata["error_message"] = (
                "Simulated tool execution failure"
            )

        event = {
            "run_id": run_id,
            "span_id": str(uuid4()),
            "name": name,
            "span_type": span_type,
            "status": status,
            "timestamp": (
                start_time + timedelta(seconds=step_number * 2)
            ).isoformat(),
            "metadata": metadata,
        }

        try:
            send_trace(event)
            print(
                f"  [{status.upper()}] "
                f"{name} ({latency_ms}ms)"
            )
        except (urllib.error.URLError, RuntimeError) as exc:
            print(f"  [FAILED TO SEND] {name}: {exc}")
            raise

        time.sleep(0.15)

    print(f"Completed {len(workflow['steps'])} spans")


def main():
    print("AgentScope Demo Trace Generator")
    print("=" * 40)

    random.seed(42)

    for index, workflow in enumerate(AGENT_WORKFLOWS):
        generate_workflow(workflow, index)

    print("\nAll demo events published successfully!")
    print("Open http://localhost:3000 to view the dashboard.")


if __name__ == "__main__":
    main()
