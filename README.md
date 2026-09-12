# HackerRank Orchestrate — Buy or Wait? AI Financial Agent

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Submission Ready](https://img.shields.io/badge/Status-Submission%20Ready-brightgreen.svg)](https://www.hackerrank.com/contests/hackerrank-orchestrate-september26/challenges/buy-or-wait/submission)

An AI-powered financial decision agent built for the **HackerRank Orchestrate** 24-hour hackathon challenge (**Buy or Wait?**).

Given user purchase/payment requests along with historical transactions, recurring commitments, minimum balance preferences, payment options, and multimodal evidence (receipt images & messages), this agent deterministically evaluates 90-day cash flow horizons to deliver safe, personalized financial decisions.

---

## 🌟 Key Features

- **90-Day Daily Cash-Flow Simulator**: Models daily balance trajectories using precise `decimal.Decimal` arithmetic to guarantee that the user's `minimum_balance_to_keep` is never breached.
- **Monotonic Safe Amount Search**: Uses binary search to determine the exact maximum amount (`amount_safe_to_pay`) safe to transfer on `request_date`.
- **Multimodal Evidence Processing**: Parses receipt images via OCR / fallback mappings (`code/evidence.py`) and resolves salary updates, contract cancellations, or payment adjustments from messages.
- **Provider Payment Option & Flexible Spending Optimizer**: Evaluates seller payment options, partial payments, and flexible spending reductions (`stop:<event_id>` / `reduce_to:<event_id>:<amount>`) to find the most affordable path.
- **Zero Token Cost & Sub-Second Execution**: Fully deterministic implementation using Python standard library primitives—processing all 250 evaluation requests in under 0.2 seconds with 0 API cost.
- **Strict Quality Gate & Validator**: 100% compliant with the official output schema (`output.csv`).

---

## 🏗 System Architecture

```text
               ┌────────────────────────┐
               │  dataset/*.csv & media │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │    code/data_loader    │
               │ (Indexed user records) │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │     code/evidence      │
               │ (OCR & message parser) │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │  code/main: build_flows│
               │ (90-day cash timeline) │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │   code/main: decide    │
               │ (Candidate selection)  │
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │       output.csv       │
               │ (250 evaluated requests│
               └───────────┬────────────┘
                           │
                           ▼
               ┌────────────────────────┐
               │    code/validator      │
               │ (0 contract violations)│
               └────────────────────────┘
```

---

## 📊 Output Schema Contract

The solution writes `output.csv` with these exact 8 required columns:

| Column | Type | Description |
|---|---|---|
| `request_id` | String | Unique request identifier |
| `amount_safe_to_pay` | Decimal | Maximum safe payment on `request_date` |
| `affordability_status` | Enum | `affordable_now`, `affordable_with_plan`, `affordable_later`, `not_affordable` |
| `recommended_payment_method` | Enum | `full_payment`, `partial_payment`, `installments`, `wait`, `not_recommended` |
| `payment_plan` | String | Chronological payment dates & amounts `YYYY-MM-DD:amount|...` or `none` |
| `earliest_date_for_full_payment` | String | Earliest conservative date for full payment (`YYYY-MM-DD` or empty) |
| `spending_changes_needed` | String | Flexible spending changes (`stop:id` / `reduce_to:id:amt`) or `none` |
| `decision_explanation` | String | Grounded, concise decision explanation |

---

## 🚀 Quick Start & Usage

### 1. Prerequisites
Python 3.11+ (Python 3.13 recommended). Standard library dependencies only.

### 2. Run Main Engine
To evaluate all requests in `dataset/requests.csv` and generate `output.csv`:

```bash
python code/main.py --dataset-dir dataset --output output.csv
```

### 3. Run Validation & Quality Gate
Run the master quality gate to execute unit tests, sample benchmarks, contract validation, and submission packaging:

```bash
python check_all.py
```

### 4. Run Unit Tests
```bash
python -m unittest discover tests
```

### 5. Package Submission Archive
To build `code.zip` containing `evaluation/usage_report.md` (and strictly excluding `dataset/`):

```bash
python package_submission.py
```

---

## 📁 Repository Structure

```text
├── AGENTS.md                  # Hackathon rules, audit logging, & submission guidelines
├── check_all.py               # Master pre-submission quality gate runner
├── package_submission.py      # Automated zip packager for submission
├── problem_statement.md       # Official HackerRank challenge specification
├── log.txt                    # Audit log of session activities and turn summaries
├── output.csv                 # Generated submission output predictions
├── code.zip                   # Final packaged code archive for HackerRank portal
├── code/                      # Core agent implementation
│   ├── main.py                # Main engine, flow builder, & decision logic
│   ├── data_loader.py         # CSV ingestion & index builder
│   ├── evidence.py            # Multimodal OCR & message parser
│   ├── validator.py           # Contract & output schema validator
│   ├── evaluate.py            # Dataset batch runner & evaluator
│   └── evaluation/
│       └── usage_report.md    # Model token usage & cost summary
├── docs/                      # Technical design & dataset reference docs
│   ├── IMPLEMENTATION_PLAN.md # Architectural plan & system design
│   ├── DATASET_REFERENCE.md   # Schema definition & data rules
│   └── AI_JUDGE_PREP.md       # Q&A prep for technical evaluation
└── tests/                     # Test suite
    ├── test_engine.py         # Automated unit tests for engine logic
    └── eval_samples.py        # Benchmark runner against 25 public sample requests
```

---

## 🏆 Benchmark & Quality Gate Results

- **Unit Tests**: 7/7 passed (`tests/test_engine.py`)
- **Sample Request Benchmark**: 100% match on recommended payment method (25/25)
- **Output Schema Validation**: 0 errors across 250 evaluation requests (`output.csv`)
- **Execution Speed**: <0.2 seconds total batch processing time
- **Cost**: $0.00 (100% deterministic, zero LLM tokens used)

---

## 🔗 Official HackerRank Submission Portal

For challenge submission, upload `code.zip` and `output.csv` at:

[HackerRank Submission Portal](https://www.hackerrank.com/contests/hackerrank-orchestrate-september26/challenges/buy-or-wait/submission)
