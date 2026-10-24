from functools import wraps


def instrument_openai(client, tracer):
    """
    Instrument synchronous OpenAI Chat Completions calls.

    Supports non-streaming requests made inside an active
    AgentScope trace.
    """
    original_create = client.chat.completions.create

    @wraps(original_create)
    def traced_create(*args, **kwargs):
        # Allow ordinary OpenAI calls outside AgentScope traces.
        if tracer.run_id is None:
            return original_create(*args, **kwargs)

        if kwargs.get("stream", False):
            raise NotImplementedError(
                "Streaming OpenAI calls are not yet supported by AgentScope"
            )

        metadata = {
            "provider": "openai",
            "model": kwargs.get("model", "unknown"),
        }

        with tracer.span(
            "openai.chat.completions",
            span_type="llm",
            metadata=metadata,
        ):
            response = original_create(*args, **kwargs)

            metadata["model"] = getattr(
                response, "model", metadata["model"]
            )

            usage = getattr(response, "usage", None)

            if usage is not None:
                metadata["prompt_tokens"] = getattr(
                    usage, "prompt_tokens", 0
                )
                metadata["completion_tokens"] = getattr(
                    usage, "completion_tokens", 0
                )
                metadata["tokens"] = getattr(
                    usage, "total_tokens", 0
                )

            return response

    client.chat.completions.create = traced_create
    return client
