"""
API Contract Validator — Main Entry Point
==========================================
Usage:
    # Run full agent evaluation (all 10 cases):
    python3 main.py evaluate

    # Run baseline (for comparison):
    python3 main.py baseline

    # Validate a single custom case:
    python3 main.py validate --spec path/to/spec.yaml --code path/to/service.py

    # Run single evaluation case:
    python3 main.py evaluate --cases case_01 case_03
"""

import os
import sys
import argparse
import json


def cmd_evaluate(args):
    from evaluation.run_evaluation import run_agent_evaluation
    cases = args.cases if args.cases else [f"case_{i:02d}" for i in range(1, 11)]
    run_agent_evaluation(cases)


def cmd_baseline(args):
    from baseline.baseline_validator import evaluate_baseline
    cases = args.cases if args.cases else [f"case_{i:02d}" for i in range(1, 11)]
    evaluate_baseline(cases)


def cmd_validate(args):
    """Validate a single custom spec+service pair."""
    from agents.orchestrator import run_validation

    if not args.spec or not args.code:
        print("Error: --spec and --code are required for single validation")
        sys.exit(1)

    with open(args.spec) as f:
        spec_content = f.read()
    with open(args.code) as f:
        code_content = f.read()

    case_id = os.path.splitext(os.path.basename(args.spec))[0]

    print(f"\nValidating: {args.spec} vs {args.code}")
    print("Running agent pipeline...\n")

    result = run_validation(
        case_id=case_id,
        spec_content=spec_content,
        code_content=code_content,
        trajectory_dir="trajectories",
    )

    print("\n" + "="*60)
    print(result["markdown_report"])
    print("="*60)
    print(f"\nViolations found: {result['violation_count']}")
    print(f"Time: {result['elapsed_seconds']}s")


def cmd_compare(args):
    """Print comparison table: baseline vs agent."""
    baseline_path = "evaluation/baseline_results.json"
    agent_path = "evaluation/agent_results.json"

    if not os.path.exists(baseline_path) or not os.path.exists(agent_path):
        print("Run both 'baseline' and 'evaluate' first to generate results.")
        return

    with open(baseline_path) as f:
        baseline = json.load(f)
    with open(agent_path) as f:
        agent = json.load(f)

    print("\n" + "="*60)
    print("BASELINE vs AGENT COMPARISON")
    print("="*60)
    print(f"{'Metric':<25} {'Baseline':>10} {'Agent':>10} {'Change':>10}")
    print("-"*60)

    def fmt_change(b, a):
        diff = a - b
        sign = "+" if diff >= 0 else ""
        return f"{sign}{diff:.3f}"

    metrics = [
        ("F1 Score", "f1"),
        ("Precision", "precision"),
        ("Recall", "recall"),
        ("Avg Time (s)", "avg_time_seconds"),
    ]
    for label, key in metrics:
        b_val = baseline.get(key, 0)
        a_val = agent.get(key, 0)
        change = fmt_change(b_val, a_val)
        print(f"  {label:<23} {b_val:>10.3f} {a_val:>10.3f} {change:>10}")

    print("-"*60)
    print(f"  {'TP/FP/FN/TN':<23} "
          f"{baseline['tp']}/{baseline['fp']}/{baseline['fn']}/{baseline['tn']:>3}   "
          f"{agent['tp']}/{agent['fp']}/{agent['fn']}/{agent['tn']:>3}")
    print("="*60)


def main():
    parser = argparse.ArgumentParser(
        description="API Contract Validator — Agentic Workflow"
    )
    subparsers = parser.add_subparsers(dest="command")

    # evaluate
    p_eval = subparsers.add_parser("evaluate", help="Run agent on all eval cases")
    p_eval.add_argument("--cases", nargs="*")

    # baseline
    p_base = subparsers.add_parser("baseline", help="Run baseline on all eval cases")
    p_base.add_argument("--cases", nargs="*")

    # validate
    p_val = subparsers.add_parser("validate", help="Validate a single spec+code pair")
    p_val.add_argument("--spec", help="Path to OpenAPI YAML spec")
    p_val.add_argument("--code", help="Path to Python FastAPI service")

    # compare
    subparsers.add_parser("compare", help="Print baseline vs agent comparison table")

    args = parser.parse_args()

    if args.command == "evaluate":
        cmd_evaluate(args)
    elif args.command == "baseline":
        cmd_baseline(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "compare":
        cmd_compare(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
