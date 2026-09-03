"""
Evaluation Runner — Agent Solution
====================================
Runs the full agent pipeline on all 10 cases and computes F1 score.
Compares against ground truth to produce the final scorecard.

Usage:
    python3 evaluation/run_evaluation.py
    python3 evaluation/run_evaluation.py --cases case_01 case_02  (subset)
"""

import os
import sys
import json
import time
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.orchestrator import run_validation
from evaluation.ground_truth import GROUND_TRUTH

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
TRAJ_DIR = os.path.join(ROOT, "trajectories")
REPORTS_DIR = os.path.join(ROOT, "reports")


def load_case(case_id: str) -> tuple[str, str]:
    spec_path = os.path.join(DATA_DIR, "specs", f"{case_id}.yaml")
    service_path = os.path.join(DATA_DIR, "services", f"{case_id}.py")
    with open(spec_path) as f:
        spec = f.read()
    with open(service_path) as f:
        code = f.read()
    return spec, code


def run_agent_evaluation(cases: list[str]) -> dict:
    results = []
    os.makedirs(REPORTS_DIR, exist_ok=True)

    print("\n" + "="*65)
    print("AGENT EVALUATION — Agentic API Contract Validator")
    print("="*65)

    for case_id in cases:
        print(f"\n  [{case_id}] Running agent pipeline...", flush=True)
        spec, code = load_case(case_id)

        # Small delay between cases to respect free tier rate limits
        if results:  # not first case
            time.sleep(8)

        try:
            result = run_validation(
                case_id=case_id,
                spec_content=spec,
                code_content=code,
                trajectory_dir=TRAJ_DIR,
            )
        except Exception as e:
            print(f"    ERROR: {e}")
            result = {
                "case_id": case_id,
                "detected_violation": False,
                "violations": [],
                "elapsed_seconds": 0,
                "error": str(e),
            }

        # Save individual markdown report
        report_path = os.path.join(REPORTS_DIR, f"{case_id}_report.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(result.get("markdown_report", "No report generated."))

        # Compare against ground truth
        truth = GROUND_TRUTH[case_id]
        predicted = result["detected_violation"]
        actual = truth["has_violations"]

        if predicted and actual:
            label = "TP"
        elif predicted and not actual:
            label = "FP"
        elif not predicted and actual:
            label = "FN"
        else:
            label = "TN"

        result["label"] = label
        result["actual_has_violation"] = actual
        results.append(result)

        # Show per-case summary
        violations_found = result.get("violation_count", 0)
        elapsed = result.get("elapsed_seconds", 0)
        print(f"    → {label} | violations_found={violations_found} | actual={actual} | {elapsed}s")
        if result["violations"]:
            for v in result["violations"]:
                print(f"       · [{v.get('type','?')}] {v.get('endpoint','?')}")

    # ─────────────────────────────────────────────
    # Compute metrics
    # ─────────────────────────────────────────────
    tp = sum(1 for r in results if r["label"] == "TP")
    fp = sum(1 for r in results if r["label"] == "FP")
    fn = sum(1 for r in results if r["label"] == "FN")
    tn = sum(1 for r in results if r["label"] == "TN")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    total_tokens = sum(r.get("total_tokens", 0) for r in results)
    avg_time = sum(r.get("elapsed_seconds", 0) for r in results) / len(results)
    # Rough cost at claude-sonnet-4-6 rates
    cost_usd = total_tokens * 9.0 / 1_000_000  # blended estimate

    print("\n" + "="*65)
    print("AGENT RESULTS SUMMARY")
    print("="*65)
    print(f"  TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(f"  Precision : {precision:.3f}")
    print(f"  Recall    : {recall:.3f}")
    print(f"  F1 Score  : {f1:.3f}  ← PRIMARY METRIC")
    print(f"  Avg time  : {avg_time:.2f}s per case")
    print(f"  Est. cost : ~${cost_usd:.4f} USD")
    print("="*65)

    summary = {
        "method": "agent_v1_orchestrated",
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "avg_time_seconds": round(avg_time, 2),
        "estimated_cost_usd": round(cost_usd, 4),
        "total_tokens": total_tokens,
        "per_case_results": [
            {
                "case_id": r["case_id"],
                "label": r["label"],
                "detected": r["detected_violation"],
                "actual": r["actual_has_violation"],
                "violation_count": r.get("violation_count", 0),
                "elapsed_seconds": r.get("elapsed_seconds", 0),
            }
            for r in results
        ],
    }

    out_path = os.path.join(ROOT, "evaluation", "agent_results.json")
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n  Results → {out_path}")
    print(f"  Reports → {REPORTS_DIR}/")
    print(f"  Trajectories → {TRAJ_DIR}/")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="*", default=None,
                        help="Specific cases to run, e.g. case_01 case_02")
    args = parser.parse_args()

    if args.cases:
        cases = args.cases
    else:
        cases = [f"case_{i:02d}" for i in range(1, 11)]

    run_agent_evaluation(cases)
