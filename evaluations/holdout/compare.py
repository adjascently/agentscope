"""Compare updated diagnosis engine against frozen holdout cases."""

import hashlib
import json
from collections import Counter
from pathlib import Path

from apps.api.app.diagnosis import diagnose_run

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "evaluations" / "holdout"

cases = json.loads((FOLDER / "cases.json").read_text())
baseline = json.loads((FOLDER / "baseline.json").read_text())

tp = fp = fn = 0
evidence_correct = evidence_total = 0
passed = 0
failures = []

for case in cases:
    result = diagnose_run(case["spans"])

    predicted = [
        (d["code"], d["evidence"]["span_id"])
        for d in result["diagnoses"]
    ]
    expected = [
        (d["code"], d["span_id"])
        for d in case["expected"]
    ]

    expected_codes = Counter(code for code, _ in expected)
    predicted_codes = Counter(code for code, _ in predicted)

    matched = sum(
        min(n, predicted_codes[code])
        for code, n in expected_codes.items()
    )

    tp += matched
    fp += len(predicted) - matched
    fn += len(expected) - matched

    evidence_correct += len(
        set(predicted) & set(expected)
    )
    evidence_total += len(expected)

    exact = (
        Counter(predicted) == Counter(expected)
        and result["status"] == case["expected_status"]
    )
    passed += int(exact)

    if not exact:
        failures.append({
            "id": case["id"],
            "expected": expected,
            "predicted": predicted,
        })

precision = tp / (tp + fp) if tp + fp else 0
recall = tp / (tp + fn) if tp + fn else 0
f1 = (
    2 * precision * recall / (precision + recall)
    if precision + recall else 0
)

summary = {
    "engine_sha256": hashlib.sha256(
        (ROOT / "apps/api/app/diagnosis.py").read_bytes()
    ).hexdigest(),
    "total_cases": len(cases),
    "exact_cases_passed": passed,
    "true_positives": tp,
    "false_positives": fp,
    "false_negatives": fn,
    "precision": round(precision, 4),
    "recall": round(recall, 4),
    "f1": round(f1, 4),
    "evidence_accuracy": round(
        evidence_correct / evidence_total, 4
    ),
}

output = {
    "baseline_summary": baseline["summary"],
    "updated_summary": summary,
    "remaining_failures": failures,
}

(FOLDER / "comparison.json").write_text(
    json.dumps(output, indent=2) + "\n"
)

print(json.dumps(summary, indent=2))
print("\nRemaining failures:", len(failures))
for failure in failures:
    print(failure["id"])

print("\nSaved evaluations/holdout/comparison.json")
