# Fraud Detection API

A production-grade fraud detection service combining **rule-based scoring** and **ML anomaly detection**. Built to demonstrate how good product thinking shapes technical architecture — every design decision maps to a product requirement.

Mock is available at https://htmlpreview.github.io/?https://github.com/dagrawal840-lab/FraudDetection/blob/claude/fraud-detection-tool-oeP8C/demo.html
---

## What It Does

Evaluates payment transactions in real time and returns one of three verdicts:

| Verdict | Score | Action |
|---------|-------|--------|
| **ALLOW** | 0–39 | Transaction proceeds |
| **REVIEW** | 40–69 | Sent to human review queue |
| **BLOCK** | 70–100 | Transaction declined |

### How the score is computed

```
final_score = (0.6 × rule_score) + (0.4 × ml_score)
```

- **Rule score** — configurable rules in `config/rules.yaml` fire and contribute weighted points
- **ML score** — Isolation Forest anomaly model trained on transaction features, normalized to 0–100
- **Blend ratio** — configurable per A/B experiment

---

## Architecture

```
POST /v1/transactions/evaluate
          │
          ▼
   Decision Engine
   ┌──────────────────────────────────────────┐
   │  1. Feature Flags (ml_scoring_enabled?)  │
   │  2. A/B Assignment (model version?)      │
   │  3. Rule Engine → rule_score             │
   │  4. ML Scorer   → ml_score               │
   │  5. Score Blend → final_score            │
   │  6. Verdict Threshold → ALLOW/REVIEW/BLOCK│
   │  7. Audit Log (async write)              │
   └──────────────────────────────────────────┘
```

### PM-Specific Design Choices

| Technical Feature | Product Purpose |
|---|---|
| YAML rule config + hot-reload | Risk analysts update rules in <1 hour, no sprint needed |
| `owner` field on every rule and flag | Clear accountability; no orphaned configs |
| Feature flags with rollout % | Safe gradual rollout; instant kill switch |
| A/B experiment framework | Ship new ML model to 20% first; graduate on data |
| Full explainability payload | Analyst investigation in <10 min; regulatory compliance |
| Per-rule hit rate metrics | Identify dead rules and over-firing rules proactively |
| Audit log (append-only) | PCI-DSS / SOC2 compliance; decision traceability |
| `REVIEW` verdict | Separates block automation from false-positive risk |

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Train the ML model
python ml/train.py

# 3. Seed demo data (optional)
python scripts/seed_data.py

# 4. Run the API
uvicorn app.main:app --reload
# → http://localhost:8000/docs
```

Or with Make:
```bash
make setup   # install + train + seed
make run     # start the API
```

---

## API Examples

### Evaluate a transaction

```bash
curl -X POST http://localhost:8000/v1/transactions/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "txn_abc123",
    "user_id": "usr_xyz789",
    "amount": 7500.00,
    "currency": "USD",
    "merchant_id": "merch_001",
    "merchant_name": "International Wire",
    "hour_of_day": 2,
    "tx_count_1h": 8,
    "tx_count_24h": 25,
    "avg_amount_30d": 250.00,
    "amount_vs_avg_ratio": 30.0,
    "is_new_device": true,
    "geo_mismatch": true,
    "is_high_risk_mcc": true
  }'
```

**Response:**
```json
{
  "event_id": "a3f2b1c4-...",
  "transaction_id": "txn_abc123",
  "user_id": "usr_xyz789",
  "verdict": "BLOCK",
  "final_score": 91.4,
  "rule_score": 100.0,
  "ml_score": 78.2,
  "rule_blend_weight": 0.6,
  "review_threshold": 40.0,
  "block_threshold": 70.0,
  "triggered_rules": [
    {"id": "high_amount", "description": "Transaction amount significantly exceeds...", "score_contribution": 40, "field": "amount", "actual_value": 7500.0},
    {"id": "velocity_1h", "description": "More than 5 transactions...", "score_contribution": 35, "field": "tx_count_1h", "actual_value": 8},
    {"id": "geo_mismatch", "description": "Transaction country differs...", "score_contribution": 30, "field": "geo_mismatch", "actual_value": true},
    {"id": "new_device", "description": "Device fingerprint not previously seen...", "score_contribution": 25, "field": "is_new_device", "actual_value": true}
  ],
  "model_version": 1,
  "experiment_id": null,
  "experiment_variant": "control",
  "ml_enabled": true,
  "latency_ms": 3.2
}
```

### Hot-reload rules (no restart)

```bash
# 1. Edit config/rules.yaml (e.g., lower the high_amount threshold)
# 2. Reload live:
curl -X PUT http://localhost:8000/v1/rules/reload
```

### View the KPI dashboard

```bash
curl http://localhost:8000/v1/metrics/dashboard
```

### Audit trail for a transaction

```bash
curl http://localhost:8000/v1/transactions/txn_abc123/audit
```

---

## Running Tests

```bash
# Full test suite with coverage
make test

# Quick run
pytest tests/ -v
```

---

## Configuration

### Tuning Detection Thresholds (`config/rules.yaml`)

Edit and reload without a restart:
- `thresholds.review` / `thresholds.block` — verdict cutoffs
- `rule_blend_weight` — how much to weight rules vs. ML
- Per-rule `score_contribution` — how aggressively each signal is weighted
- Per-rule `enabled` — instantly activate/deactivate a rule

### Feature Flags (`config/feature_flags.yaml`)

| Flag | Default | Purpose |
|------|---------|---------|
| `ml_scoring_enabled` | 100% | ML scoring on/off |
| `new_velocity_model` | 20% | Gradual rollout of v2 velocity features |
| `strict_geo_check` | 0% | Pending legal review |
| `async_audit_log` | 100% | Non-blocking audit writes |

### A/B Experiments (`config/ab_experiments.yaml`)

Active experiment: **exp_ml_model_v2** — testing ML model v2 on 20% of traffic.

---

## Project Structure

```
├── app/
│   ├── core/          # Rule engine, ML scorer, decision engine, flags, A/B testing
│   ├── api/           # FastAPI routes and Pydantic models
│   ├── services/      # Audit logger, metrics collector, model registry
│   └── db/            # SQLAlchemy models and database setup
├── config/            # YAML configs (rules, feature flags, experiments)
├── ml/                # Model training, evaluation, and artifacts
├── docs/              # PRD, metrics definitions, runbook
├── tests/             # Pytest test suite
└── scripts/           # seed_data.py for demo data
```

---

## Documentation

- [Product Requirements Document](docs/PRD.md) — problem statement, user stories, launch plan
- [Metrics Guide](docs/METRICS.md) — KPI definitions, targets, alert thresholds
- [Operations Runbook](docs/RUNBOOK.md) — incident response, routine operations
- [Interactive API Docs](http://localhost:8000/docs) — Swagger UI (when running)
