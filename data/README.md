# PaySim Data

Place the PaySim CSV here before running ingestion or training scripts.

## How to get the data

### Option A — Kaggle CLI (recommended)
```bash
pip install kaggle
# Place your kaggle.json API token at ~/.kaggle/kaggle.json
kaggle datasets download -d ealaxi/paysim1
unzip paysim1.zip -d data/
mv data/PS_*.csv data/paysim.csv   # or rename as needed
```

### Option B — Manual download
1. Go to: https://www.kaggle.com/datasets/ealaxi/paysim1
2. Download the zip, extract the CSV
3. Rename it to `data/paysim.csv`

## Schema

| Column | Type | Description |
|--------|------|-------------|
| step | int | 1-hour time unit (1–743, ~30 days) |
| type | str | CASH-IN, CASH-OUT, DEBIT, PAYMENT, TRANSFER |
| amount | float | Transaction amount |
| nameOrig | str | Originating account ID |
| oldbalanceOrg | float | Balance before transaction |
| newbalanceOrig | float | Balance after transaction |
| nameDest | str | Destination account/merchant |
| oldbalanceDest | float | Destination balance before |
| newbalanceDest | float | Destination balance after |
| isFraud | int | Ground truth label (1 = fraud) |
| isFlaggedFraud | int | Flagged by naive rule (amount > 200,000) |

## Size
~6.3M rows, ~493MB uncompressed.
Use `--sample 50000` flag on scripts to work with a subset.
