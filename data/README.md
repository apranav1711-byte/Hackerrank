# Local dataset setup

The official challenge dataset is intentionally not committed to this repository and must not be included in the uploaded code archive. Clone the official starter repository beside this repository:

```bash
gh repo clone interviewstreet/hackerrank-orchestrate-september26 ../hackerrank-orchestrate-september26
```

Then run the scaffold with:

```bash
python3 code/main.py --dataset-dir ../hackerrank-orchestrate-september26/dataset --output output.csv
```

Alternatively set:

```bash
export DATASET_DIR=/path/to/hackerrank-orchestrate-september26/dataset
```

The final upload archive should contain the `code/` directory and its documentation, but not this challenge dataset, the `dataset/` directory, virtual environments, `node_modules`, or build artifacts.
