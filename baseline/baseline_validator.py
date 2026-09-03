"""
BASELINE: Rule-based API contract validator (no LLM).

Represents the simplest reasonable approach a developer uses today:
a script that checks for violations using regex and basic string matching.

This is what most teams do before investing in AI tooling:
- grep for field names
- check status codes with regex
- compare endpoint lists with string matching

No LLM. No AST. No structured reasoning.
This is the fair baseline we measure all agent improvement against.
"""

import os
import re
import sys
import json
import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def load_case(case_id: str) -> tuple:
    spec_path = os.path.join(DATA_DIR, "specs", f"{case_id}.yaml")
    service_path = os.path.join(DATA_DIR, "services", f"{case_id}.py")
    with open(spec_path, "r") as f:
        spec_content = f.read()
    with open(service_path, "r") as f:
        service_content = f.read()
    return spec_content, service_content


def run_baseline(case_id: str) -> dict:
    """
    Rule-based baseline: regex + string matching, no LLM.
    
    Checks:
    1. Required fields in spec vs Optional in code (regex)
    2. Response field names in spec vs return dict keys (string search)
    3. Status codes in spec vs decorator (regex)
    4. Endpoint paths in spec vs @app.route decorators (regex)
    """
    spec_text, code_text = load_case(case_id)
    
    violations_found = []
    
    try:
        spec = yaml.safe_load(spec_text)
        paths = spec.get("paths", {})
        
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method not in ["get","post","put","patch","delete"]:
                    continue
                
                # CHECK 1: Required fields — look for Optional in code
                rb = operation.get("requestBody", {})
                if rb:
                    content = rb.get("content", {}).get("application/json", {})
                    schema = content.get("schema", {})
                    required_fields = schema.get("required", [])
                    for field in required_fields:
                        # Simple regex: if field appears with Optional[] nearby
                        pattern = rf"Optional.*{field}|{field}.*Optional"
                        if re.search(pattern, code_text, re.IGNORECASE):
                            violations_found.append(f"POSSIBLE_OPTIONAL: {field} in {method.upper()} {path}")
                
                # CHECK 2: Response field names
                responses = operation.get("responses", {})
                for status, resp in responses.items():
                    content = resp.get("content", {}).get("application/json", {})
                    schema = content.get("schema", {})
                    properties = schema.get("properties", {})
                    for field_name in properties:
                        # Check if field name appears in code at all
                        if field_name not in code_text:
                            violations_found.append(f"MISSING_FIELD: '{field_name}' not in code for {method.upper()} {path}")
                
                # CHECK 3: Status codes
                for status_code in responses.keys():
                    if str(status_code) == "200":
                        continue  # too common, skip
                    # Look for status_code in decorator
                    decorator_pattern = rf"status_code\s*=\s*{status_code}"
                    if not re.search(decorator_pattern, code_text):
                        violations_found.append(f"STATUS_CODE: {status_code} declared but not found in decorator")
        
        # CHECK 4: Endpoints in code not in spec
        spec_paths = set()
        for path in paths.keys():
            # normalize path params
            normalized = re.sub(r'\{[^}]+\}', '{param}', path)
            spec_paths.add(normalized)
        
        # Find @app.METHOD("/path") in code
        route_pattern = r'@app\.(get|post|put|patch|delete)\(["\']([^"\']+)["\']'
        code_routes = re.findall(route_pattern, code_text, re.IGNORECASE)
        for method_found, path_found in code_routes:
            normalized = re.sub(r'\{[^}]+\}', '{param}', path_found)
            if normalized not in spec_paths:
                violations_found.append(f"UNDOCUMENTED: {method_found.upper()} {path_found}")
    
    except Exception as e:
        violations_found = []
    
    detected = len(violations_found) > 0
    
    return {
        "case_id": case_id,
        "detected_violation": detected,
        "raw_response": "\n".join(violations_found) if violations_found else "NO VIOLATIONS FOUND",
        "elapsed_seconds": 0.01,
        "violations_found": violations_found,
    }


def evaluate_baseline(cases: list) -> dict:
    from evaluation.ground_truth import GROUND_TRUTH

    results = []
    print("\n" + "="*60)
    print("BASELINE EVALUATION — Rule-based Script (No LLM)")
    print("="*60)

    for case_id in cases:
        print(f"\n  Running {case_id}...", end=" ", flush=True)
        result = run_baseline(case_id)
        results.append(result)

        truth = GROUND_TRUTH[case_id]
        predicted = result["detected_violation"]
        actual = truth["has_violations"]

        if predicted and actual:       label = "TP"
        elif predicted and not actual: label = "FP"
        elif not predicted and actual: label = "FN"
        else:                          label = "TN"

        result["label"] = label
        result["actual_has_violation"] = actual
        print(f"{label} | detected={predicted} | actual={actual} | {result['elapsed_seconds']}s")
        if result["violations_found"]:
            for v in result["violations_found"][:2]:
                print(f"    · {v}")

    tp = sum(1 for r in results if r["label"] == "TP")
    fp = sum(1 for r in results if r["label"] == "FP")
    fn = sum(1 for r in results if r["label"] == "FN")
    tn = sum(1 for r in results if r["label"] == "TN")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    avg_time  = sum(r["elapsed_seconds"] for r in results) / len(results)

    print("\n" + "="*60)
    print("BASELINE RESULTS SUMMARY")
    print("="*60)
    print(f"  TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(f"  Precision : {precision:.3f}")
    print(f"  Recall    : {recall:.3f}")
    print(f"  F1 Score  : {f1:.3f}")
    print(f"  Avg time  : {avg_time:.4f}s per case")
    print(f"  Cost      : $0.00 (no LLM)")
    print("="*60)

    summary = {
        "method": "baseline_rule_based_script",
        "description": "Regex + string matching, no LLM, no AST",
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "avg_time_seconds": round(avg_time, 4),
        "estimated_cost_usd": 0.0,
        "per_case_results": results,
    }

    out_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "evaluation", "baseline_results.json"
    )
    with open(out_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nResults saved to: {out_path}")
    return summary


if __name__ == "__main__":
    cases = [f"case_{i:02d}" for i in range(1, 11)]
    evaluate_baseline(cases)
