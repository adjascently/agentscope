"""Reproducible entry point for AgentScope's 100-case evaluation."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "evaluations"


def run_script(filename):
    print(f"\nRunning {filename}...", flush=True)
    subprocess.run(
        [sys.executable, str(EVAL_DIR / filename)],
        cwd=ROOT,
        check=True,
    )


run_script("evaluate_diagnosis.py")
run_script("evaluate_extra.py")

base = json.loads((EVAL_DIR / "results.json").read_text())
combined = json.loads((EVAL_DIR / "results_100.json").read_text())

assert base["summary"]["total_cases"] == 80
assert combined["summary"]["total_cases"] == 100
assert len(combined["extra_cases"]) == 20

summary = combined["summary"]

print("\n" + "=" * 45)
print("AGENTSCOPE — 100-CASE EVALUATION")
print("=" * 45)
print(f"Total cases:       {summary['total_cases']}")
print(f"Precision:         {summary['precision']:.2%}")
print(f"Recall:            {summary['recall']:.2%}")
print(f"F1 score:          {summary['f1']:.2%}")
print(f"Evidence accuracy: {summary['evidence_accuracy']:.2%}")
print(f"Extra cases passed:{summary['extra_cases_passed']}/20")
print("=" * 45)

print("\nDetailed results:")
print("  evaluations/results.json")
print("  evaluations/results_100.json")
