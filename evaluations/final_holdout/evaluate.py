"""Final synthetic holdout: frozen engine, 150 labeled scenarios."""

import hashlib
import json
from collections import Counter
from pathlib import Path
from uuid import uuid5, NAMESPACE_DNS

from apps.api.app.diagnosis import diagnose_run

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "evaluations" / "final_holdout"
ENGINE = ROOT / "apps/api/app/diagnosis.py"
FROZEN = "ca6c4cebb473aa49bbbd10600d8cef75d6584e7e6493a64d23057bcf5d137b93"

actual = hashlib.sha256(ENGINE.read_bytes()).hexdigest()
assert actual == FROZEN, "Engine changed since freeze!"

if (OUT / "baseline.json").exists():
    raise SystemExit("Baseline exists; refusing to overwrite.")

cases = []


def uid(value):
    return str(uuid5(NAMESPACE_DNS, "agentscope-final-" + value))


def add(category, specs, expected):
    cid = f"{category}-{sum(c['category'] == category for c in cases):02d}"
    spans = []
    for name, status, metadata, parent in specs:
        spans.append({
            "span_id": uid(cid + "/" + name),
            "parent_span_id": uid(cid + "/" + parent) if parent else None,
            "name": name,
            "span_type": "llm" if "llm" in name else "tool",
            "status": status,
            "metadata": metadata,
        })
    cases.append({
        "id": cid,
        "category": category,
        "spans": spans,
        "expected_status": "error" if any(
            s["status"] == "error" for s in spans
        ) else "ok",
        "expected": [
            {"code": code, "span_id": uid(cid + "/" + name)}
            for code, name in expected
        ],
    })


def msg(text):
    return {"error_message": text}


# 30 provider and protocol variations
provider_examples = [
    ("rate_limited", "HTTP 429: retry after 30 seconds"),
    ("rate_limited", "Anthropic overloaded_error"),
    ("rate_limited", "RESOURCE_EXHAUSTED: requests per minute"),
    ("rate_limited", "Upstream throttling detected"),
    ("rate_limited", "rate_limit_exceeded"),
    ("quota_exhausted", "Monthly spend limit reached"),
    ("quota_exhausted", "billing_hard_limit_reached"),
    ("quota_exhausted", "insufficient_quota"),
    ("quota_exhausted", "Project credits depleted"),
    ("quota_exhausted", "credit_balance_exhausted"),
    ("authentication_failed", "PermissionDenied: invalid token"),
    ("authentication_failed", "401 Unauthorized"),
    ("authentication_failed", "UNAUTHENTICATED"),
    ("authentication_failed", "invalid_api_key"),
    ("authentication_failed", "Expired API token"),
    ("timeout", "DEADLINE_EXCEEDED"),
    ("timeout", "ReadTimeout"),
    ("timeout", "Request timed out"),
    ("timeout", "Socket deadline exceeded"),
    ("timeout", "Gateway timeout 504"),
    ("connection_failed", "ECONNREFUSED"),
    ("connection_failed", "ECONNRESET"),
    ("connection_failed", "DNS lookup failure"),
    ("connection_failed", "Connection refused"),
    ("connection_failed", "TLS handshake failed"),
    ("unknown_error", "Internal provider error"),
    ("unknown_error", "Tool returned invalid JSON"),
    ("unknown_error", "Unexpected runtime exception"),
    ("unknown_error", "Unsupported response format"),
    ("unknown_error", "Model output validation failed"),
]
for code, message in provider_examples:
    add("providers", [
        ("llm", "error", msg(message), None)
    ], [(code, "llm")])


# 25 misleading or conflicting evidence scenarios
for i in range(25):
    variants = [
        ({"error_code": "rate_limit_exceeded",
          "error_message": "Connection refused"}, "rate_limited"),
        ({"error_code": "invalid_api_key",
          "error_message": "Request timed out"}, "authentication_failed"),
        ({"error_code": "insufficient_quota",
          "error_message": "rate limit exceeded"}, "quota_exhausted"),
        (msg("Schema validation failed: 'timeout' is a field name"),
         "unknown_error"),
        (msg("Parser error: input includes 'rate limit'"),
         "unknown_error"),
    ]
    metadata, code = variants[i % 5]
    add("conflicting", [
        ("llm", "error", metadata, None)
    ], [(code, "llm")])


# 25 nested failure chains
for i in range(25):
    code, message = [
        ("timeout", "Request timed out"),
        ("rate_limited", "rate_limit_exceeded"),
        ("connection_failed", "Connection refused"),
        ("authentication_failed", "invalid_api_key"),
        ("quota_exhausted", "insufficient_quota"),
    ][i % 5]
    add("nested", [
        ("agent", "error", msg(message), None),
        ("planner", "error", msg(message), "agent"),
        ("tool", "error", msg(message), "planner"),
        ("llm", "error", msg(message), "tool"),
    ], [(code, "llm")])


# 20 independent simultaneous failures
for i in range(20):
    first = [
        ("timeout", "Request timed out"),
        ("rate_limited", "rate_limit_exceeded"),
    ][i % 2]
    second = [
        ("connection_failed", "Connection refused"),
        ("authentication_failed", "invalid_api_key"),
    ][i % 2]
    add("multiple", [
        ("agent", "ok", {}, None),
        ("llm_a", "error", msg(first[1]), "agent"),
        ("llm_b", "error", msg(second[1]), "agent"),
    ], [(first[0], "llm_a"), (second[0], "llm_b")])


# 20 malformed or absent metadata cases
malformed = [
    {}, None, {"error_message": None},
    {"error_message": 429},
    {"error_message": ["rate limit"]},
    {"error_message": {"reason": "timeout"}},
    {"error_code": ["invalid_api_key"]},
    {"error_type": {"type": "APITimeoutError"}},
    {"error_message": True},
    {"error_message": ""},
]
for i in range(20):
    add("malformed", [
        ("llm", "error", malformed[i % len(malformed)], None)
    ], [("unknown_error", "llm")])


# 15 successful or false-positive trap scenarios
for i in range(15):
    if i % 3 == 0:
        specs = [("agent", "ok", {}, None)]
    elif i % 3 == 1:
        specs = [
            ("agent", "ok", {}, None),
            ("llm", "ok", msg("rate_limit_exceeded"), "agent"),
        ]
    else:
        specs = [
            ("agent", "ok", {}, None),
            ("llm", "ok", msg("Request timed out"), "agent"),
        ]
    add("success", specs, [])


# 15 unusual but recognizable / unrecognizable formats
unusual = [
    ("timeout", "TimeoutError: task exceeded deadline"),
    ("rate_limited", "Rate limit exceeded: retry later"),
    ("authentication_failed", "AuthenticationError: bad key"),
    ("connection_failed", "ConnectionError: remote unreachable"),
    ("quota_exhausted", "insufficient_quota"),
    ("unknown_error", "Unhandled KeyError"),
    ("unknown_error", "Output schema mismatch"),
    ("unknown_error", "Unknown agent state"),
    ("timeout", "APITimeoutError"),
    ("rate_limited", "rate_limit_error"),
    ("connection_failed", "Connection refused"),
    ("authentication_failed", "401 unauthorized"),
    ("unknown_error", "AssertionError in agent"),
    ("quota_exhausted", "credit_balance_exhausted"),
    ("unknown_error", "Invalid tool parameters"),
]
for code, message in unusual:
    add("unusual", [
        ("llm", "error", msg(message), None)
    ], [(code, "llm")])


assert len(cases) == 150
assert dict(Counter(c["category"] for c in cases)) == {
    "providers": 30,
    "conflicting": 25,
    "nested": 25,
    "multiple": 20,
    "malformed": 20,
    "success": 15,
    "unusual": 15,
}

dataset_text = json.dumps(cases, indent=2) + "\n"
(OUT / "cases.json").write_text(dataset_text)

tp = fp = fn = 0
evidence_correct = evidence_total = 0
exact_passed = 0
results = []

for case in cases:
    exception = None
    try:
        result = diagnose_run(case["spans"])
        predicted = [
            {
                "code": d["code"],
                "span_id": d["evidence"]["span_id"],
            }
            for d in result["diagnoses"]
        ]
        status = result["status"]
    except Exception as exc:
        exception = f"{type(exc).__name__}: {exc}"
        predicted = []
        status = "exception"

    expected = case["expected"]
    ec = Counter(d["code"] for d in expected)
    pc = Counter(d["code"] for d in predicted)

    matched = sum(min(count, pc[code]) for code, count in ec.items())
    tp += matched
    fp += len(predicted) - matched
    fn += len(expected) - matched

    ep = Counter((d["code"], d["span_id"]) for d in expected)
    pp = Counter((d["code"], d["span_id"]) for d in predicted)
    evidence_correct += sum((ep & pp).values())
    evidence_total += len(expected)

    passed = (
        exception is None
        and status == case["expected_status"]
        and ep == pp
    )
    exact_passed += int(passed)

    results.append({
        "id": case["id"],
        "category": case["category"],
        "passed": passed,
        "expected": expected,
        "predicted": predicted,
        "exception": exception,
    })


def divide(a, b):
    return round(a / b, 4) if b else None


precision = divide(tp, tp + fp)
recall = divide(tp, tp + fn)
f1 = (
    round(2 * precision * recall / (precision + recall), 4)
    if precision is not None and recall is not None
    and precision + recall
    else 0.0
)

summary = {
    "engine_sha256": actual,
    "dataset_sha256": hashlib.sha256(
        dataset_text.encode()
    ).hexdigest(),
    "total_cases": 150,
    "exact_cases_passed": exact_passed,
    "exact_case_accuracy": divide(exact_passed, 150),
    "true_positives": tp,
    "false_positives": fp,
    "false_negatives": fn,
    "precision": precision,
    "recall": recall,
    "f1": f1,
    "evidence_accuracy": divide(
        evidence_correct, evidence_total
    ),
    "evidence_correct": evidence_correct,
    "evidence_total": evidence_total,
    "exceptions": sum(
        r["exception"] is not None for r in results
    ),
    "category_counts": dict(
        Counter(c["category"] for c in cases)
    ),
    "limitations": [
        "Synthetic, manually constructed cases.",
        "Designed with knowledge of the existing engine.",
        "Some examples reuse known patterns.",
        "Not representative of production incidents.",
        "First-run results are preserved without retuning.",
    ],
}

(OUT / "baseline.json").write_text(
    json.dumps({
        "summary": summary,
        "cases": results,
    }, indent=2) + "\n"
)

print("\nFINAL HOLDOUT RESULTS")
print(json.dumps(summary, indent=2))

print("\nFailed scenarios:")
for r in results:
    if not r["passed"]:
        print(
            r["id"],
            "| expected:", [x["code"] for x in r["expected"]],
            "| predicted:", [x["code"] for x in r["predicted"]],
            "| exception:", r["exception"],
        )

print("\nSaved evaluations/final_holdout/baseline.json")
