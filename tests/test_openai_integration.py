from types import SimpleNamespace
from unittest.mock import Mock

from agentscope import AgentScope, instrument_openai


def main():
    # Fake OpenAI response; no API credits required.
    response = SimpleNamespace(
        model="gpt-4o-mini",
        usage=SimpleNamespace(
            prompt_tokens=20,
            completion_tokens=15,
            total_tokens=35,
        ),
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="Kafka provides durable event streaming."
                )
            )
        ],
    )

    create = Mock(return_value=response)

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create)
        )
    )

    tracer = AgentScope(endpoint="http://localhost:8000")
    instrument_openai(client, tracer)

    with tracer.trace("openai-success-test") as run_id:
        result = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "Explain Kafka"}
            ],
        )

        print("Response:", result.choices[0].message.content)

    assert create.call_count == 1

    print("Run ID:", run_id)
    print("Expected tokens: 35")
    print("Success! Check AgentScope dashboard.")


if __name__ == "__main__":
    main()
