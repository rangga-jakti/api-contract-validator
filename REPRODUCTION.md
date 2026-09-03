# Reproduction Guide

A second person starting from a clean environment should be able to follow these steps and reproduce F1 = 0.615 (baseline) and F1 = 1.000 (agent).

---

## Requirements

- Python 3.10+
- Groq API key (free tier at console.groq.com)
- Internet connection

**Tested on:** Python 3.12 (Windows 11), Python 3.12 (Ubuntu 24.04)  
**Runtime:** ~30s (baseline), ~35s (agent evaluation, 10 cases)  
**Cost:** $0.00 (Groq free tier)  
**Model:** `qwen/qwen3.8-27b` via Groq

---

## Setup

```bash
# 1. Clone or extract the project
cd api-contract-validator

# 2. Install dependencies
pip install -r requirements.txt

# 3. Set Groq API key
# Linux/Mac:
export GROQ_API_KEY="gsk_..."

# Windows PowerShell:
$env:GROQ_API_KEY = "gsk_..."

# Permanent (Windows):
[System.Environment]::SetEnvironmentVariable("GROQ_API_KEY", "gsk_...", "User")
```

---

## Run Baseline

```bash
python main.py baseline
```

**Expected output:**
```
BASELINE RESULTS SUMMARY
  TP=4  FP=0  FN=5  TN=1
  Precision : 1.000
  Recall    : 0.444
  F1 Score  : 0.615
  Avg time  : 0.0100s per case
  Cost      : $0.00 (no LLM)
```

Saves to: `evaluation/baseline_results.json`

---

## Run Agent Evaluation

```bash
python main.py evaluate
```

**Expected output:**
```
AGENT RESULTS SUMMARY
  TP=9  FP=0  FN=0  TN=1
  Precision : 1.000
  Recall    : 1.000
  F1 Score  : 1.000
  Avg time  : ~2.84s per case
```

Saves to:
- `evaluation/agent_results.json`
- `reports/case_XX_report.md` (one per case)
- `trajectories/case_XX_trajectory.json` (one per case)

---

## Compare Results

```bash
python main.py compare
```

---

## Validate a Custom Spec+Service Pair

```bash
python main.py validate --spec path/to/spec.yaml --code path/to/service.py
```

---

## Data

All evaluation data is synthetic — created for this project.
- `data/specs/case_01.yaml` through `case_10.yaml` — OpenAPI 3.0 specs
- `data/services/case_01.py` through `case_10.py` — FastAPI services
- `evaluation/ground_truth.py` — known violations for scoring

No external data sources required.

---

## Versions

```
python        3.12
groq          0.9.0+
pyyaml        6.0+
fastapi       0.110.0+
Model         qwen/qwen3.8-27b (via Groq)
```
