"""Frozen-engine holdout evaluation for AgentScope."""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from uuid import NAMESPACE_DNS, uuid5

from apps.api.app.diagnosis import diagnose_run

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evaluations" / "holdout"
ENGINE = ROOT / "apps" / "api" / "app" / "diagnosis.py"

FROZEN_SHA = (
    "dbe09b53a4f882ce2dc0aaeed259c907306d73"
    "c075fe960920b2ad29709da9e3"
)

actual_sha = hashlib.sha256(ENGINE.read_bytes()).hexdigest()
if actual_sha != FROZEN_SHA:
    raise SystemExit(
        "Diagnosis engine changed since freeze. "
        "Do not overwrite the baseline."
    )


def uid(key):
    return str(uuid5(NAMESPACE_DNS, "agentscope-holdout-" + key))


def span(case_id, name, status="ok", metadata=None, parent=None):
    return {
        "span_id": uid(f"{case_id}/{name}"),
        "parent_span_id": parent,
        "name": name,
        "span_type": "llm" if "llm" in name else "tool",
        "status": status,
        "metadata": metadata if metadata is not None else {},
    }


cases = []


def add(category, index, specs, expected):
    case_id = f"{category}-{index:02d}"
    spans = []
    for name, status, metadata, parent_name in specs:
        parent = uid(f"{case_id}/{parent_name}") if parent_name else None
        spans.append(span(case_id, name, status, metadata, parent))

    cases.append({
        "id": case_id,
        "category": category,
        "spans": spans,
        "expected_status": (
            "error" if any(s["status"] == "error" for s in spans)
            else "ok"
        ),
        "expected": [
            {"code": code, "span_id": uid(f"{case_id}/{name}")}
            for code, name in expected
        ],
    })


def err(message):
    return {"error_message": message}


# 1. Unfamiliar wording — 20
wording = [
    ("quota_exhausted", "Billing quota has been depleted"),
    ("quota_exhausted", "No remaining credits for this project"),
    ("rate_limited", "HTTP 429 Too Many Requests"),
    ("rate_limited", "Request throttled by upstream provider"),
    ("authentication_failed", "HTTP 401 invalid credentials"),
    ("authentication_failed", "Unauthorized: expired API token"),
    ("timeout", "DeadlineExceeded after 30 seconds"),
    ("timeout", "Request deadline was exceeded"),
    ("connection_failed", "ECONNRESET by peer"),
    ("connection_failed", "DNS resolution failed"),
    ("quota_exhausted", "insufficient_quota"),
    ("rate_limited", "rate_limit_exceeded"),
    ("authentication_failed", "invalid_api_key"),
    ("timeout", "ReadTimeout while fetching response"),
    ("connection_failed", "Connection refused by localhost"),
    ("unknown_error", "Unexpected serialization exception"),
    ("unknown_error", "Tool returned invalid JSON"),
    ("unknown_error", "Unrecognized plugin response"),
    ("unknown_error", "ValueError in tool arguments"),
    ("unknown_error", "Agent failed for unspecified reason"),
]
for i, (code, message) in enumerate(wording):
    add("wording", i, [
        ("llm", "error", err(message), None),
    ], [(code, "llm")])


# 2. Provider-specific error formats — 15
providers = [
    ("quota_exhausted", {"error_code": "insufficient_quota"}),
    ("rate_limited", {"error_code": "rate_limit_exceeded"}),
    ("authentication_failed", {"error_code": "invalid_api_key"}),
    ("timeout", {"error_type": "APITimeoutError"}),
    ("connection_failed", {"error_type": "APIConnectionError"}),
    ("rate_limited", err("Anthropic: rate_limit_error")),
    ("authentication_failed", err("Anthropic authentication_error")),
    ("rate_limited", err("Gemini RESOURCE_EXHAUSTED")),
    ("authentication_failed", err("Gemini UNAUTHENTICATED")),
    ("quota_exhausted", err("OpenAI insufficient_quota")),
    ("rate_limited", err("OpenAI rate_limit_exceeded")),
    ("authentication_failed", err("OpenAI invalid_api_key")),
    ("timeout", err("Anthropic request timed out")),
    ("connection_failed", err("Gemini connection error")),
    ("unknown_error", err("Provider INTERNAL server failure")),
]
for i, (code, metadata) in enumerate(providers):
    add("providers", i, [
        ("llm", "error", metadata, None),
    ], [(code, "llm")])


# 3. Nested failures — 15
for i in range(15):
    code, message = [
        ("rate_limited", "rate_limit_exceeded"),
        ("timeout", "Request timed out"),
        ("connection_failed", "Connection refused"),
    ][i % 3]

    add("nested", i, [
        ("agent", "error", err(message), None),
        ("planner", "error", err(message), "agent"),
        ("tool", "error", err(message), "planner"),
        ("llm", "error", err(message), "tool"),
    ], [(code, "llm")])


# 4. Conflicting metadata — 15
conflicts = [
    ("rate_limited", {"error_code": "rate_limit_exceeded",
                      "error_message": "Request timed out"}),
    ("quota_exhausted", {"error_code": "insufficient_quota",
                         "error_message": "rate limit exceeded"}),
    ("authentication_failed", {"error_code": "invalid_api_key",
                               "error_message": "Connection refused"}),
    ("timeout", {"error_type": "APITimeoutError",
                 "error_message": "Connection refused"}),
    ("connection_failed", {"error_type": "APIConnectionError",
                           "error_message": "Request timed out"}),
]
for i in range(15):
    code, metadata = conflicts[i % len(conflicts)]
    add("conflicts", i, [
        ("llm", "error", metadata, None),
    ], [(code, "llm")])


# 5. Missing/malformed metadata — 10
missing = [
    {},
    {"error_message": ""},
    {"error_message": None},
    {"error_message": 500},
    {"error_message": {"detail": "timeout"}},
    {"error_code": "unrecognized"},
    {"error_type": "UnexpectedException"},
    {"error_message": []},
    {"error_message": " "},
    {"error_message": "unclassified failure"},
]
for i, metadata in enumerate(missing):
    add("missing_metadata", i, [
        ("llm", "error", metadata, None),
    ], [("unknown_error", "llm")])


# 6. Identical errors on independent spans — 10
for i in range(10):
    message = [
        "Request timed out",
        "rate_limit_exceeded",
    ][i % 2]
    code = "timeout" if i % 2 == 0 else "rate_limited"
    add("duplicates", i, [
        ("tool_a", "error", err(message), None),
        ("tool_b", "error", err(message), None),
    ], [(code, "tool_a"), (code, "tool_b")])


# 7. Multiple independent failures — 10
for i in range(10):
    add("multiple", i, [
        ("agent", "ok", {}, None),
        ("llm", "error", err("insufficient_quota"), "agent"),
        ("tool", "error", err("Connection refused"), "agent"),
    ], [
        ("quota_exhausted", "llm"),
        ("connection_failed", "tool"),
    ])


# 8. Mixed successful and failed spans — 5
for i in range(5):
    if i == 0:
        add("mixed", i, [
            ("agent", "ok", {}, None),
            ("llm", "ok", {}, "agent"),
        ], [])
    else:
        add("mixed", i, [
            ("agent", "ok", {}, None),
            ("successful_tool", "ok", {}, "agent"),
            ("failed_tool", "error",
             err("Request timed out"), "agent"),
        ], [("timeout", "failed_tool")])


assert len(cases) == 100

counts = Counter(c["category"] for c in cases)
assert counts == {
    "wording": 20,
    "providers": 15,
    "nested": 15,
    "conflicts": 15,
    "missing_metadata": 10,
    "duplicates": 10,
    "multiple": 10,
    "mixed": 5,
}

dataset_path = OUT / "cases.json"
baseline_path = OUT / "baseline.json"

if baseline_path.exists():
    raise SystemExit(
        "Baseline already exists. Refusing to overwrite it."
    )

dataset_text = json.dumps(cases, indent=2) + "\n"
dataset_path.write_text(dataset_text)

tp = fp = fn = 0
evidence_correct = evidence_total = 0
exact_passes = 0
results = []

for case in cases:
    exception = None
    try:
        output = diagnose_run(case["spans"])
        predicted = [
            {
                "code": d["code"],
                "span_id": d["evidence"]["span_id"],
            }
            for d in output["diagnoses"]
        ]
        status = output["status"]
    except Exception as exc:
        exception = f"{type(exc).__name__}: {exc}"
        predicted = []
        status = "exception"

    expected = case["expected"]
    expected_codes = Counter(d["code"] for d in expected)
    predicted_codes = Counter(d["code"] for d in predicted)

    matched = sum(
        min(n, predicted_codes[code])
        for code, n in expected_codes.items()
    )

    tp += matched
    fp += len(predicted) - matched
    fn += len(expected) - matched

    expected_pairs = {
        (d["code"], d["span_id"]) for d in expected
    }
    predicted_pairs = {
        (d["code"], d["span_id"]) for d in predicted
    }

    evidence_correct += len(expected_pairs & predicted_pairs)
    evidence_total += len(expected)

    passed = (
        exception is None
        and status == case["expected_status"]
        and Counter(
            (d["code"], d["span_id"]) for d in predicted
        ) == Counter(
            (d["code"], d["span_id"]) for d in expected
        )
    )

    exact_passes += int(passed)
    results.append({
        "id": case["id"],
        "category": case["category"],
        "passed": passed,
        "expected": expected,
        "predicted": predicted,
        "exception": exception,
    })


def ratio(n, d):
    return round(n / d, 4) if d else None


precision = ratio(tp, tp + fp)
recall = ratio(tp, tp + fn)
f1 = (
    round(2 * precision * recall / (precision + recall), 4)
    if precision is not None and recall is not None
    and precision + recall
    else 0.0
)

summary = {
    "engine_sha256": actual_sha,
    "dataset_sha256": hashlib.sha256(
        dataset_text.encode()
    ).hexdigest(),
    "total_cases": len(cases),
    "category_counts": dict(counts),
    "exact_cases_passed": exact_passes,
    "true_positives": tp,
    "false_positives": fp,
    "false_negatives": fn,
    "precision": precision,
    "recall": recall,
    "f1": f1,
    "evidence_accuracy": ratio(
        evidence_correct, evidence_total
    ),
    "evidence_correct": evidence_correct,
    "evidence_total": evidence_total,
    "exceptions": sum(
        r["exception"] is not None for r in results
    ),
    "limitations": [
        "Synthetic, manually designed holdout cases.",
        "Not a production incident sample.",
        "Some cases share patterns with development tests.",
        "Labels and assumptions require review.",
        "Do not interpret results as production accuracy.",
    ],
}

baseline_path.write_text(
    json.dumps({
        "summary": summary,
        "cases": results,
    }, indent=2) + "\n"
)

print(json.dumps(summary, indent=2))
print("\nFailed cases:")
for result in results:
    if not result["passed"]:
        print(
            result["id"],
            "expected:", [x["code"] for x in result["expected"]],
            "predicted:", [x["code"] for x in result["predicted"]],
            "exception:", result["exception"],
        )

print("\nSaved:", baseline_path)
