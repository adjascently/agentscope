"""Deterministic, evidence-backed diagnosis of AI agent failures."""

def diagnose_run(spans: list[dict]) -> dict:
    diagnoses = []
    seen = set()

    # Diagnose leaf failures first, rather than their parent agent spans.
    error_spans = [
        span for span in spans
        if span.get("status") == "error"
    ]

    parent_ids = {
        str(span["parent_span_id"])
        for span in error_spans
        if span.get("parent_span_id")
    }

    for span in error_spans:
        # A failed parent often repeats its child's exception.
        if str(span["span_id"]) in parent_ids:
            continue

        metadata = span.get("metadata") or {}
        message = str(metadata.get("error_message", ""))
        lower = message.lower()

        if "credit_balance_exhausted" in lower or "insufficient_quota" in lower:
            code = "quota_exhausted"
            title = "OpenAI API credits exhausted"
            explanation = "The API rejected the request because the project has no available credits."
            fix = "Add API credits or switch to a funded OpenAI project. Retrying without resolving billing will not help."

        elif "rate_limit_exceeded" in lower or "rate limit" in lower or "rate_limit_error" in lower:
            code = "rate_limited"
            title = "API rate limit exceeded"
            explanation = "The provider rejected the request due to a request or token rate limit."
            fix = "Reduce request concurrency and use bounded exponential backoff. Check the provider's rate limits."

        elif "timeout" in lower or "timed out" in lower:
            code = "timeout"
            title = "Request timed out"
            explanation = "The operation exceeded its allowed execution time."
            fix = "Inspect the slow operation, configure an appropriate timeout, and retry transient failures with limits."

        elif "authenticationerror" in lower or "invalid_api_key" in lower or "incorrect api key" in lower or "401 unauthorized" in lower:
            code = "authentication_failed"
            title = "API authentication failed"
            explanation = "The provider rejected the supplied credentials."
            fix = "Check the API key, project permissions, and environment configuration. Never log the key itself."

        elif "connection refused" in lower or "connectionerror" in lower or "connection error" in lower:
            code = "connection_failed"
            title = "Service connection failed"
            explanation = "The operation could not establish a connection to a dependency."
            fix = "Check the service endpoint, network connectivity, and dependency health."

        else:
            code = "unknown_error"
            title = "Unclassified execution failure"
            explanation = "The span failed, but its error does not match a known diagnosis rule."
            fix = "Inspect the error message and surrounding spans to identify the cause."

        # Deduplicate repeated leaf failures with the same classification/message.
        fingerprint = (code, message)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)

        diagnoses.append({
            "code": code,
            "title": title,
            "explanation": explanation,
            "suggested_fix": fix,
            "evidence": {
                "span_id": str(span["span_id"]),
                "span_name": span.get("name"),
                "error_message": message,
            },
        })

    return {
        "status": "error" if error_spans else "ok",
        "diagnosis_count": len(diagnoses),
        "diagnoses": diagnoses,
    }
