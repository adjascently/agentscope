"""Reproducible synthetic evaluation of AgentScope's diagnosis engine."""

import json
from collections import Counter
from pathlib import Path
from uuid import uuid5, NAMESPACE_DNS

from apps.api.app.diagnosis import diagnose_run

MESSAGES = {
    "quota_exhausted": [
        "Error code: 429 - credit_balance_exhausted",
        "OpenAI insufficient_quota",
    ],
    "rate_limited": [
        "Rate limit exceeded",
        "rate_limit_exceeded",
    ],
    "authentication_failed": [
        "AuthenticationError: invalid credentials",
        "invalid_api_key",
    ],
    "timeout": [
        "Request timed out",
        "Connection timeout",
    ],
    "connection_failed": [
        "Connection refused",
        "ConnectionError: service unreachable",
    ],
    "unknown_error": [
        "Unexpected parser exception",
        "Tool returned invalid JSON",
    ],
}

def make_id(value):
    return str(uuid5(NAMESPACE_DNS, f"agentscope-eval-{value}"))

def span(case_id, suffix, status, message="", parent=None):
    return {
        "span_id": make_id(f"{case_id}-{suffix}"),
        "parent_span_id": parent,
        "name": f"operation.{suffix}",
        "span_type": "llm" if suffix == "llm" else "agent",
        "status": status,
        "metadata": {"error_message": message} if message else {},
    }

cases = []

for category, messages in MESSAGES.items():
    for i in range(10):
        case_id = f"{category}-{i}"
        root = span(case_id, "root", "ok")
        llm = span(
            case_id, "llm", "error",
            messages[i % len(messages)],
            root["span_id"],
        )
        cases.append({
            "id": case_id,
            "category": category,
            "spans": [root, llm],
            "expected_code": category,
            "expected_evidence": llm["span_id"],
        })

for i in range(10):
    case_id = f"success-{i}"
    root = span(case_id, "root", "ok")
    llm = span(case_id, "llm", "ok", parent=root["span_id"])
    cases.append({
        "id": case_id,
        "category": "success",
        "spans": [root, llm],
        "expected_code": None,
        "expected_evidence": None,
    })

for i in range(10):
    case_id = f"propagated-{i}"
    message = "Error code: 429 - credit_balance_exhausted"
    root = span(case_id, "root", "error", message)
    llm = span(case_id, "llm", "error", message, root["span_id"])
    cases.append({
        "id": case_id,
        "category": "propagated",
        "spans": [root, llm],
        "expected_code": "quota_exhausted",
        "expected_evidence": llm["span_id"],
    })

assert len(cases) == 80

tp = fp = fn = 0
evidence_correct = 0
evidence_total = 0
results = []

for case in cases:
    result = diagnose_run(case["spans"])
    diagnoses = result["diagnoses"]
    predicted = [d["code"] for d in diagnoses]
    expected = case["expected_code"]

    if expected is None:
        fp += len(predicted)
    else:
        matches = sum(code == expected for code in predicted)
        tp += min(matches, 1)
        fp += len(predicted) - min(matches, 1)
        fn += int(matches == 0)
        evidence_total += 1
        if (
            len(diagnoses) == 1
            and diagnoses[0]["code"] == expected
            and diagnoses[0]["evidence"]["span_id"] == case["expected_evidence"]
        ):
            evidence_correct += 1

    results.append({
        "id": case["id"],
        "category": case["category"],
        "expected_code": expected,
        "predicted_codes": predicted,
        "expected_evidence": case["expected_evidence"],
        "predicted_evidence": [
            d["evidence"]["span_id"] for d in diagnoses
        ],
    })

precision = tp / (tp + fp) if tp + fp else 0
recall = tp / (tp + fn) if tp + fn else 0
f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
evidence_accuracy = evidence_correct / evidence_total if evidence_total else 0

summary = {
    "dataset": "Synthetic, deterministic, template-generated",
    "total_cases": len(cases),
    "category_counts": dict(Counter(c["category"] for c in cases)),
    "true_positives": tp,
    "false_positives": fp,
    "false_negatives": fn,
    "precision": round(precision, 4),
    "recall": round(recall, 4),
    "f1": round(f1, 4),
    "evidence_accuracy": round(evidence_accuracy, 4),
    "evidence_correct": evidence_correct,
    "evidence_total": evidence_total,
    "limitations": [
        "Synthetic template-generated scenarios, not production incidents.",
        "Scenarios overlap with the engine's existing keyword rules.",
        "Metrics do not establish generalization to unseen failures.",
        "No performance or latency benchmarks are claimed.",
    ],
}

output = Path("evaluations")
output.mkdir(exist_ok=True)
(output / "results.json").write_text(json.dumps({
    "summary": summary,
    "cases": results,
}, indent=2) + "\n")

print(json.dumps(summary, indent=2))
print("\nSaved evaluations/results.json")
