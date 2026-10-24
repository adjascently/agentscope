import os

from openai import OpenAI
from agentscope import AgentScope, instrument_openai


def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY before running the demo")

    tracer = AgentScope(endpoint="http://localhost:8000")
    client = instrument_openai(OpenAI(max_retries=0), tracer)

    with tracer.trace("research-assistant") as run_id:
        print(f"AgentScope run ID: {run_id}")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Explain how Apache Kafka helps build "
                        "reliable AI agent observability systems "
                        "in two sentences."
                    ),
                }
            ],
        )

        print(response.choices[0].message.content)

    print(f"Trace complete: {run_id}")


if __name__ == "__main__":
    main()
