import json
from pathlib import Path
from collections import Counter
from apps.api.app.diagnosis import diagnose_run

folder = Path("evaluations/final_holdout")
cases = json.loads((folder / "cases.json").read_text())
baseline = json.loads((folder / "baseline.json").read_text())

passed = 0
tp = fp = fn = 0
evidence_correct = evidence_total = 0
failures = []

for case in cases:
    try:
        result = diagnose_run(case["spans"])
        predicted = [
            (d["code"], d["evidence"]["span_id"])
            for d in result["diagnoses"]
        ]
        status = result["status"]
        error = None
    except Exception as exc:
        predicted = []
        status = "exception"
        error = str(exc)

    expected = [
        (d["code"], d["span_id"])
        for d in case["expected"]
    ]

    ec = Counter(code for code, _ in expected)
    pc = Counter(code for code, _ in predicted)

    matched = sum(min(count, pc[code]) for code, count in ec.items())
    tp += matched
    fp += len(predicted) - matched
    fn += len(expected) - matched

    evidence_correct += sum(
        (Counter(expected) & Counter(predicted)).values()
    )
    evidence_total += len(expected)

    exact = (
        error is None
        and status == case["expected_status"]
        and Counter(predicted) == Counter(expected)
    )

    passed += int(exact)

    if not exact:
        failures.append({
            "id": case["id"],
            "expected": expected,
            "predicted": predicted,
            "error": error,
        })

precision = tp / (tp + fp) if tp + fp else 0
recall = tp / (tp + fn) if tp + fn else 0
f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0

summary = {
    "total_cases": len(cases),
    "exact_cases_passed": passed,
    "exact_case_accuracy": round(passed / len(cases), 4),
    "precision": round(precision, 4),
    "recall": round(recall, 4),
    "f1": round(f1, 4),
    "evidence_accuracy": round(evidence_correct / evidence_total, 4),
}

output = {
    "original_baseline": baseline["summary"],
    "post_tuning": summary,
    "remaining_failures": failures,
}

(folder / "comparison.json").write_text(json.dumps(output, indent=2))

print("\nAGENTSCOPE — FINAL HOLDOUT COMPARISON")
print(f"Original accuracy: {baseline['summary']['exact_case_accuracy']:.2%}")
print(f"Updated accuracy:  {summary['exact_case_accuracy']:.2%}")
print(f"Cases passed:      {passed}/{len(cases)}")
print(f"Precision:         {precision:.2%}")
print(f"Recall:            {recall:.2%}")
print(f"F1 score:          {f1:.2%}")
print(f"Evidence accuracy: {summary['evidence_accuracy']:.2%}")
print(f"Remaining failures: {len(failures)}")

for failure in failures:
    print(failure)
