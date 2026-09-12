# HackerRank Orchestrate — Buy or Wait?

This repository is a handoff-ready implementation workspace for the HackerRank Orchestrate September 2026 challenge. The goal is to build an AI-assisted financial decision agent that processes the supplied challenge dataset and writes one safe, personalized recommendation for every request.

## Important distinction: development data versus submission archive

The challenge dataset is supplied separately through the starter repository. Keep it locally at `dataset/` while developing, or set `DATASET_DIR` to its location. HackerRank's platform instructions say the uploaded code archive must exclude the `dataset/` folder, data corpus, virtual environments, `node_modules`, and build artifacts. The completed predictions file `output.csv` and chat transcript `log.txt` are uploaded separately.

The original starter repository and authoritative rules are at [interviewstreet/hackerrank-orchestrate-september26](https://github.com/interviewstreet/hackerrank-orchestrate-september26).

## Challenge in one paragraph

For each row in `dataset/requests.csv`, determine the maximum amount safe to pay on the request date, whether the complete request is affordable now, with a plan, later, or not at all, the safest eligible payment method, the payment schedule, the earliest safe date for full payment, any permitted flexible-spending changes, and a concise explanation. Safety requires completing the plan by the requested deadline, covering essential expenses, and never dropping below the user's preferred minimum balance during the 90-day forecast.

## Recommended stack

The solution is intentionally a Python batch application rather than a UI-first web product. Use Python 3.11+, `csv`, `datetime`, `decimal`, `pathlib`, `re`, and `collections` for the deterministic engine. `pandas`, `Pillow`, `python-dateutil`, and `pytest` are optional conveniences. An LLM or vision model may be used selectively for ambiguous messages, images, and grounded explanations, but all arithmetic, eligibility, ranking, and validation must remain deterministic.

## Quick start

From the repository root, with the challenge dataset available at `../hackerrank-orchestrate-september26/dataset/`:

```bash
python3 code/main.py --dataset-dir ../hackerrank-orchestrate-september26/dataset --output output.csv
python3 code/evaluate.py --dataset-dir ../hackerrank-orchestrate-september26/dataset --output output.csv
```

The current scaffold writes conservative baseline rows and is designed to be replaced or extended during implementation. The complete plan is in [`docs/IMPLEMENTATION_PLAN.md`](docs/IMPLEMENTATION_PLAN.md).

## Repository map

| Path | Purpose |
|---|---|
| `code/main.py` | Production entry point |
| `code/data_loader.py` | CSV loading and indexes |
| `code/forecasting.py` | Forecasting and safe-payment calculations |
| `code/planner.py` | Payment-plan candidate generation and ranking |
| `code/evidence.py` | Messages, images, and conflict-resolution hooks |
| `code/validator.py` | Output contract and safety validation |
| `code/evaluate.py` | Required evaluation workflow |
| `code/evaluation/usage_report.md` | Final model-token and cost report |
| `docs/IMPLEMENTATION_PLAN.md` | End-to-end build plan |
| `docs/DATASET_REFERENCE.md` | Dataset schemas and interpretation rules |
| `docs/AI_JUDGE_PREP.md` | Interview preparation |
| `data/README.md` | How to place the local dataset without committing it |
| `tests/` | Deterministic tests to add while implementing |

## Required output

The generated `output.csv` must have exactly these columns, in this order:

```text
request_id,amount_safe_to_pay,affordability_status,recommended_payment_method,payment_plan,earliest_date_for_full_payment,spending_changes_needed,decision_explanation
```

## Submission checklist

Before submission, generate and verify the final `output.csv`, create `code.zip` from the `code/` directory while excluding the dataset and development artifacts, and provide `log.txt` as the chat transcript. Include `code/evaluation/usage_report.md` in the code archive. The mandatory submission URL from the challenge instructions is:

<https://www.hackerrank.com/contests/hackerrank-orchestrate-september26/challenges/buy-or-wait/submission>

## Build order

First make a valid batch pipeline. Next implement the 90-day simulator and compare against the 25 public samples. Then add evidence extraction, recurrence detection, payment-option optimization, spending changes, explanations, and final packaging. A UI is optional and should only be attempted after the CSV engine and validator are reliable.
