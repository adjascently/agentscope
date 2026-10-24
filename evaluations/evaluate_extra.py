"""Twenty additional adversarial AgentScope diagnosis scenarios."""

import json
from pathlib import Path
from uuid import uuid5, NAMESPACE_DNS

from apps.api.app.diagnosis import diagnose_run


def uid(value):
    return str(uuid5(NAMESPACE_DNS, f"agentscope-extra-{value}"))


def make_span(case, name, status, message="", parent=None):
    return {
        "span_id": uid(f"{case}-{name}"),
        "parent_span_id": parent,
        "name": name,
        "span_type": "llm" if name == "llm" else "tool",
        "status": status,
        "metadata": {"error_message": message} if message else {},
    }


cases = []

# Ten scenarios containing two independent failures.
for i in range(10):
    case = f"multi-{i}"
    root = make_span(case, "root", "ok")
    llm = make_span(
        case, "llm", "error",
        "rate_limit_exceeded",
        root["span_id"],
    )
    tool = make_span(
        case, "tool", "error",
        "Connection refused",
        root["span_id"],
    )

    cases.append({
        "id": case,
        "category": "multiple_failures",
        "spans": [root, llm, tool],
        "expected": {
            ("rate_limited", llm["span_id"]),
            ("connection_failed", tool["span_id"]),
        },
    })


# Ten scenarios containing misleading error-message keywords.
for i in range(10):
    case = f"ambiguous-{i}"
    root = make_span(case, "root", "ok")

    message = (
        "Validation failed: input text contains 'rate limit', "
        "but this is a schema error"
        if i % 2 == 0
        else "Parser error: string 'timeout' is not a valid field"
    )

    llm = make_span(
        case, "llm", "error",
        message,
        root["span_id"],
    )

    cases.append({
        "id": case,
        "category": "ambiguous",
        "spans": [root, llm],
        "expected": {
            ("unknown_error", llm["span_id"]),
        },
    })


assert len(cases) == 20

tp = fp = fn = 0
evidence_correct = evidence_total = 0
results = []

for case in cases:
    output = diagnose_run(case["spans"])

    predicted = [
        (d["code"], d["evidence"]["span_id"])
        for d in output["diagnoses"]
    ]

    expected = case["expected"]

    # Classification metrics: match code counts, independently
    # of whether the supporting span is correct.
    from collections import Counter
    expected_codes = Counter(code for code, _ in expected)
    predicted_codes = Counter(code for code, _ in predicted)
    matched = sum(
        min(count, predicted_codes[code])
        for code, count in expected_codes.items()
    )

    tp += matched
    fp += len(predicted) - matched
    fn += len(expected) - matched

    evidence_total += len(expected)
    evidence_correct += len(set(predicted) & expected)

    results.append({
        "id": case["id"],
        "category": case["category"],
        "expected": sorted([list(x) for x in expected]),
        "predicted": [list(x) for x in predicted],
        "passed": set(predicted) == expected,
    })

original = json.loads(Path("evaluations/results.json").read_text())
base = original["summary"]

tp += base["true_positives"]
fp += base["false_positives"]
fn += base["false_negatives"]
evidence_correct += base["evidence_correct"]
evidence_total += base["evidence_total"]

precision = tp / (tp + fp) if tp + fp else 0
recall = tp / (tp + fn) if tp + fn else 0
f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0

summary = {
    "dataset": "100 deterministic synthetic scenarios",
    "total_cases": base["total_cases"] + len(cases),
    "true_positives": tp,
    "false_positives": fp,
    "false_negatives": fn,
    "precision": round(precision, 4),
    "recall": round(recall, 4),
    "f1": round(f1, 4),
    "evidence_accuracy": round(evidence_correct / evidence_total, 4),
    "evidence_correct": evidence_correct,
    "evidence_total": evidence_total,
    "extra_cases_passed": sum(r["passed"] for r in results),
    "extra_cases_total": 20,
    "limitations": [
        "Synthetic template-generated scenarios, not production incidents.",
        "The first 80 cases reuse known diagnosis keywords.",
        "Adversarial examples are limited and manually constructed.",
        "Results do not establish production accuracy.",
    ],
}

Path("evaluations/results_100.json").write_text(
    json.dumps({
        "summary": summary,
        "extra_cases": results,
    }, indent=2) + "\n"
)

print(json.dumps(summary, indent=2))
print("\nSaved evaluations/results_100.json")
