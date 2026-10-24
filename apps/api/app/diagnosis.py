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
    """Classify provider failures using structured evidence first."""
    import re

    if not isinstance(metadata, dict):
        return "unknown_error"

    def normalize(value):
        return value.lower().strip() if isinstance(value, str) else ""

    message = normalize(metadata.get("error_message"))
    code = normalize(
        metadata.get("error_code")
        or metadata.get("provider_error_code")
    )
    error_type = normalize(metadata.get("error_type"))

    # Explicit provider codes have the highest priority.
    code_map = {
        "credit_balance_exhausted": "quota_exhausted",
        "insufficient_quota": "quota_exhausted",
        "billing_hard_limit_reached": "quota_exhausted",
        "rate_limit_exceeded": "rate_limited",
        "rate_limit_error": "rate_limited",
        "resource_exhausted": "rate_limited",
        "invalid_api_key": "authentication_failed",
        "authentication_error": "authentication_failed",
        "unauthenticated": "authentication_failed",
    }

    if code in code_map:
        return code_map[code]

    type_map = {
        "apitimeouterror": "timeout",
        "timeouterror": "timeout",
        "deadlineexceeded": "timeout",
        "deadline_exceeded": "timeout",
        "apiconnectionerror": "connection_failed",
        "connectionerror": "connection_failed",
    }

    if error_type in type_map:
        return type_map[error_type]

    # Explicit HTTP status metadata, when present.
    status = metadata.get("http_status") or metadata.get("status_code")

    if status is not None:
        try:
            status = int(status)
        except (TypeError, ValueError):
            status = None

    if status == 401:
        return "authentication_failed"

    if status == 429:
        return "rate_limited"

    if status in (408, 504):
        return "timeout"

    # Avoid interpreting quoted keywords inside parser errors.
    if any(x in message for x in (
        "validation failed",
        "parser error",
        "schema error",
    )):
        return "unknown_error"

    patterns = [
        ("quota_exhausted", [
            r"credit_balance_exhausted",
            r"insufficient_quota",
            r"billing_hard_limit_reached",
            r"monthly spend limit reached",
            r"project credits depleted",
            r"billing quota.*depleted",
            r"no remaining credits",
        ]),
        ("rate_limited", [
            r"rate[_ ]limit",
            r"too many requests",
            r"\b429\b",
            r"resource_exhausted",
            r"request throttled",
            r"upstream throttling",
            r"overloaded_error",
        ]),
        ("authentication_failed", [
            r"authenticationerror",
            r"authentication_error",
            r"invalid_api_key",
            r"incorrect api key",
            r"\b401\b",
            r"unauthenticated",
            r"expired api token",
            r"permissiondenied.*invalid token",
        ]),
        ("timeout", [
            r"timeout",
            r"timed out",
            r"deadline.?exceeded",
            r"deadline was exceeded",
            r"gateway timeout",
        ]),
        ("connection_failed", [
            r"connection refused",
            r"connectionerror",
            r"connection error",
            r"econnreset",
            r"econnrefused",
            r"dns (resolution|lookup) fail",
            r"tls handshake failed",
        ]),
    ]

    for diagnosis, expressions in patterns:
        if any(re.search(pattern, message) for pattern in expressions):
            return diagnosis

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
