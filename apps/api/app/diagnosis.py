"""Deterministic, evidence-backed diagnosis of AI agent failures."""

import re


RULES = {
    "quota_exhausted": {
        "title": "OpenAI API credits exhausted",
        "explanation": "The provider rejected the request because available API credits or quota were exhausted.",
        "suggested_fix": "Check API billing, quota, and project limits. Add credits or use a funded project.",
    },
    "rate_limited": {
        "title": "API rate limit exceeded",
        "explanation": "The provider rejected the request due to a request or token rate limit.",
        "suggested_fix": "Reduce concurrency, inspect rate-limit headers, and use bounded exponential backoff.",
    },
    "authentication_failed": {
        "title": "API authentication failed",
        "explanation": "The provider rejected the supplied credentials.",
        "suggested_fix": "Check API credentials, project permissions, and environment configuration.",
    },
    "timeout": {
        "title": "Request timed out",
        "explanation": "The operation exceeded its allowed execution time.",
        "suggested_fix": "Inspect the slow operation, configure appropriate timeouts, and retry transient failures carefully.",
    },
    "connection_failed": {
        "title": "Service connection failed",
        "explanation": "The operation could not establish a connection to a dependency.",
        "suggested_fix": "Check the endpoint, network connectivity, DNS, and dependency health.",
    },
    "unknown_error": {
        "title": "Unclassified execution failure",
        "explanation": "The available evidence does not establish a recognized root cause.",
        "suggested_fix": "Inspect the originating span and surrounding events to identify the failure.",
    },
}


def classify_error(metadata: dict) -> str:
    message = str(metadata.get("error_message") or "")
    lower = message.lower()

    # Prefer explicit structured provider metadata when available.
    error_code = str(
        metadata.get("error_code")
        or metadata.get("provider_error_code")
        or ""
    ).lower()

    error_type = str(metadata.get("error_type") or "").lower()

    if error_code in {"credit_balance_exhausted", "insufficient_quota"}:
        return "quota_exhausted"

    if error_code in {"rate_limit_exceeded", "rate_limit_error"}:
        return "rate_limited"

    if error_code in {"invalid_api_key", "authentication_error"}:
        return "authentication_failed"

    if error_type in {"timeouterror", "apitimeouterror"}:
        return "timeout"

    if error_type in {"connectionerror", "apiconnectionerror"}:
        return "connection_failed"

    # Validation/parser errors can quote keywords without indicating
    # the actual cause. Do not classify quoted content as provider failure.
    if (
        re.search(r"\b(validation failed|parser error|schema error)\b", lower)
        and not error_code
        and not error_type
    ):
        return "unknown_error"

    if (
        "credit_balance_exhausted" in lower
        or "insufficient_quota" in lower
    ):
        return "quota_exhausted"

    if (
        "rate_limit_exceeded" in lower
        or "rate_limit_error" in lower
        or "rate limit" in lower
    ):
        return "rate_limited"

    if (
        "authenticationerror" in lower
        or "invalid_api_key" in lower
        or "incorrect api key" in lower
        or "401 unauthorized" in lower
    ):
        return "authentication_failed"

    if "timeout" in lower or "timed out" in lower:
        return "timeout"

    if (
        "connection refused" in lower
        or "connectionerror" in lower
        or "connection error" in lower
    ):
        return "connection_failed"

    return "unknown_error"


def diagnose_run(spans: list[dict]) -> dict:
    error_spans = [
        span for span in spans
        if span.get("status") == "error"
    ]

    # Prefer leaf failures: a failed parent often reports the same
    # exception that originated in its child.
    parent_ids = {
        str(span["parent_span_id"])
        for span in error_spans
        if span.get("parent_span_id")
    }

    diagnoses = []

    for span in error_spans:
        span_id = str(span["span_id"])

        if span_id in parent_ids:
            continue

        metadata = span.get("metadata") or {}
        code = classify_error(metadata)
        rule = RULES[code]

        diagnoses.append({
            "code": code,
            **rule,
            "evidence": {
                "span_id": span_id,
                "span_name": span.get("name"),
                "error_message": str(
                    metadata.get("error_message") or ""
                ),
            },
        })

    return {
        "status": "error" if error_spans else "ok",
        "diagnosis_count": len(diagnoses),
        "diagnoses": diagnoses,
    }
