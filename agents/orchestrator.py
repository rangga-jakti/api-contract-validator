"""
Orchestrator Agent — API Contract Validator
==========================================
Pipeline:
  1. Spec Parser  (deterministic, no LLM) → structured contract
  2. Code Analyzer (deterministic, no LLM) → structured code facts
  3. Detector Agent (LLM)  → find violations with full context
  4. Report Writer (LLM)   → actionable markdown report

Uses: Groq API (free tier) - qwen/qwen3.8-27b
"""

import os
import sys
import json
import time
from groq import Groq
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.spec_parser import parse_spec, format_contract_summary
from tools.code_analyzer import analyze_code, format_code_summary

MODEL = "qwen/qwen3.8-27b"


def _call_llm(prompt: str) -> str:
    """Call Groq API with retry on rate limit."""
    client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.1,
            )
            return response.choices[0].message.content
        except Exception as e:
            if "rate" in str(e).lower() or "429" in str(e):
                wait = (attempt + 1) * 10
                print(f"\n    [rate limit] waiting {wait}s...", flush=True)
                time.sleep(wait)
            else:
                raise
    return ""


def _safe_parse_json(text: str) -> dict:
    text = text.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
    return {"violations": [], "error": "JSON parse failed", "raw": text[:300]}


def run_validation(case_id: str, spec_content: str, code_content: str,
                   trajectory_dir: str = None) -> dict:
    """Full agentic validation pipeline."""
    trajectory = []
    start_total = time.time()

    def log(step: str, data: dict):
        entry = {"step": step,
                 "timestamp": datetime.utcnow().isoformat(),
                 "elapsed_seconds": round(time.time() - start_total, 2),
                 **data}
        trajectory.append(entry)
        return entry

    # ── STEP 1: Spec Parser (deterministic) ──────────────────
    log("spec_parser_start", {"input": "OpenAPI YAML"})
    parsed_spec = parse_spec(spec_content)
    spec_summary = format_contract_summary(parsed_spec)
    log("spec_parser_complete", {
        "endpoints_found": len(parsed_spec["endpoints"]),
        "endpoint_list": parsed_spec["endpoint_paths"],
    })

    # ── STEP 2: Code Analyzer (deterministic) ────────────────
    log("code_analyzer_start", {"input": "Python FastAPI source"})
    analyzed_code = analyze_code(code_content)
    code_summary = format_code_summary(analyzed_code)
    log("code_analyzer_complete", {
        "endpoints_found": len(analyzed_code["endpoints"]),
        "endpoint_list": analyzed_code["endpoint_paths"],
        "models_found": list(analyzed_code["models"].keys()),
    })

    # ── STEP 3: Deterministic endpoint diff ──────────────────
    spec_paths = set(parsed_spec["endpoint_paths"])
    code_paths = set(analyzed_code["endpoint_paths"])
    deterministic_undocumented = code_paths - spec_paths

    undoc_violations = []
    for ep in deterministic_undocumented:
        undoc_violations.append({
            "type": "UNDOCUMENTED_ENDPOINT",
            "endpoint": ep,
            "spec_says": f"Not documented. Spec has: {list(spec_paths)}",
            "code_does": f"Endpoint {ep} registered in router",
            "evidence": f"Deterministic diff: {ep} in code, not in spec",
            "confidence": "HIGH"
        })

    log("deterministic_diff", {
        "spec_endpoints": list(spec_paths),
        "code_endpoints": list(code_paths),
        "undocumented": list(deterministic_undocumented),
    })

    # ── STEP 4: Detector Agent (LLM) ─────────────────────────
    detector_prompt = f"""You are a precise API contract validator. Find ALL violations where code contradicts the OpenAPI spec.

SPEC CONTRACT (parsed from OpenAPI YAML):
{spec_summary}

CODE ANALYSIS (parsed from Python AST — includes Pydantic models, return fields, raised exceptions):
{code_summary}

VIOLATION TYPES TO CHECK:
1. MISSING_REQUIRED_PARAM   — spec marks field required[], code has it as Optional or with a default value
2. FIELD_NAME_MISMATCH      — spec names a response field one way, code returns a different name (e.g. spec: price, code: cost)
3. STATUS_CODE_MISMATCH     — spec declares a response status code, code decorator or default returns a different one
4. RESPONSE_FIELD_RENAME    — response field name differs between spec and code (e.g. spec: token, code: access_token)
5. BEHAVIOR_CONTRADICTION   — spec says requestBody required:false (optional), but code raises HTTPException(400) when body is empty
6. PARAM_NAME_MISMATCH      — spec defines query params with certain names, code function uses different param names
7. SECURITY_MISSING         — spec has a required header parameter, code function does not accept or validate it
8. TYPE_MISMATCH            — spec declares a field as integer, code returns a string value for that field

HOW TO CHECK EACH TYPE:
- For MISSING_REQUIRED_PARAM: compare spec required[] list vs Pydantic model required/optional fields
- For FIELD_NAME_MISMATCH: compare spec response properties vs code return fields or module var fields
- For STATUS_CODE_MISMATCH: compare spec response status code vs code declared_status_code
- For BEHAVIOR_CONTRADICTION: if spec requestBody required=False AND code raises HTTPException(status=400) → violation
- For PARAM_NAME_MISMATCH: compare spec query params names vs code function arg names
- For SECURITY_MISSING: if spec has header_params with required=True, check if code has matching Header() args
- For TYPE_MISMATCH: if spec says integer but code return value is clearly a string (e.g. "write", "read")

RULES:
- Only report violations with direct evidence from the summaries above
- Each violation needs a specific spec fact AND a specific code fact
- If everything matches, return empty violations array

Respond ONLY with valid JSON (no markdown, no extra text):
{{
  "violations": [
    {{
      "type": "VIOLATION_TYPE",
      "endpoint": "METHOD /path",
      "spec_says": "exact fact from spec summary",
      "code_does": "exact fact from code summary",
      "evidence": "specific line or field from analysis",
      "confidence": "HIGH|MEDIUM|LOW"
    }}
  ],
  "reasoning": "one sentence summary of analysis"
}}"""

    log("detector_start", {"agent": "Detector"})
    t0 = time.time()
    detect_raw = _call_llm(detector_prompt)
    detector_result = _safe_parse_json(detect_raw)
    llm_violations = detector_result.get("violations", [])

    # Merge LLM + deterministic violations, deduplicate
    all_violations = llm_violations + undoc_violations
    seen = set()
    verified_violations = []
    for v in all_violations:
        key = (v.get("type", ""), v.get("endpoint", ""))
        if key not in seen:
            seen.add(key)
            verified_violations.append(v)

    log("detector_complete", {
        "agent": "Detector",
        "elapsed_seconds": round(time.time() - t0, 2),
        "llm_violations": len(llm_violations),
        "deterministic_violations": len(undoc_violations),
        "total_after_dedup": len(verified_violations),
        "raw_preview": detect_raw[:600],
    })

    # ── STEP 5: Report Writer (LLM) ──────────────────────────
    report_prompt = f"""You are an API compliance report writer. Write a clear, actionable developer report.

CASE: {case_id}
VERIFIED VIOLATIONS:
{json.dumps(verified_violations, indent=2)}

Write a concise markdown report a developer can act on immediately.
- No violations: confirm compliance and why it passed
- Each violation: explain impact and how to fix it
- Professional, precise, no filler text

# API Contract Validation Report: {case_id}

## Summary
[1-2 sentences: compliant or N violations found]

## Violations Found
[numbered list, or "None — fully compliant"]

## Details
[per violation: endpoint, what spec says, what code does, how to fix]

## Recommendation
[one clear action item]"""

    log("report_writer_start", {"agent": "ReportWriter"})
    t0 = time.time()
    report_text = _call_llm(report_prompt)
    log("report_writer_complete", {
        "agent": "ReportWriter",
        "elapsed_seconds": round(time.time() - t0, 2),
    })

    # ── Final Result ──────────────────────────────────────────
    total_elapsed = round(time.time() - start_total, 2)
    result = {
        "case_id": case_id,
        "detected_violation": len(verified_violations) > 0,
        "violations": verified_violations,
        "violation_count": len(verified_violations),
        "markdown_report": report_text,
        "elapsed_seconds": total_elapsed,
        "trajectory": trajectory,
    }

    if trajectory_dir:
        os.makedirs(trajectory_dir, exist_ok=True)
        traj_path = os.path.join(trajectory_dir, f"{case_id}_trajectory.json")
        with open(traj_path, "w", encoding="utf-8") as f:
            json.dump({"case_id": case_id, "trajectory": trajectory}, f, indent=2)

    return result
