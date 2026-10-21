
import sys
import time
from pathlib import Path

# Make our local SDK importable without publishing it to PyPI.
sdk_path = Path(__file__).resolve().parents[2] / "packages" / "python-sdk"
sys.path.insert(0, str(sdk_path))

from agentscope import AgentScope


scope = AgentScope(endpoint="http://127.0.0.1:8000")

print("Starting AgentScope SDK test...")

with scope.trace("SDK Demo Agent") as run_id:
    print(f"Run ID: {run_id}")

    with scope.span("fetch_documents", span_type="tool"):
        time.sleep(0.4)
        print("Documents fetched")

    with scope.span(
        "generate_summary",
        span_type="llm",
        metadata={"model": "demo-model", "tokens": 250},
    ):
        time.sleep(0.7)
        print("Summary generated")

    try:
        with scope.span("validate_output", span_type="tool"):
            time.sleep(0.2)
            raise ValueError("Demo validation failed")
    except ValueError:
        print("Validation error caught; agent recovered")

    with scope.span("final_response", span_type="agent"):
        time.sleep(0.1)
        print("Final response ready")

print("SDK test completed!")
