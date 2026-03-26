# KPI Definitions and Success Criteria
## Fraud Detection API

**Owner:** Fraud Risk + Engineering
**Reporting Cadence:** Hourly (operational), Daily (team review), Weekly (exec summary)
**Dashboard Endpoint:** `GET /v1/metrics/dashboard`

---

## Primary Metrics

### 1. `fraud_block_rate`
**Definition:** Fraction of evaluated transactions with verdict = BLOCK.
**Formula:** `blocked_count / total_evaluated`
**Target:** ≥ 0.8%
**Alert Threshold:** < 0.4% (under-detection) or > 5% (potential over-blocking)
**Window:** Rolling 24h
**Owner:** Fraud Risk
**Notes:** This is the north-star metric. An increase indicates we are catching more fraud. However, it must be read alongside the guardrail metric (false positive rate) — an increase driven by over-blocking is a problem, not a success.

---

### 2. `review_rate`
**Definition:** Fraction of evaluated transactions with verdict = REVIEW.
**Formula:** `reviewed_count / total_evaluated`
**Target:** ≤ 3%
**Alert Threshold:** > 8% (review queue overload risk)
**Window:** Rolling 1h
**Owner:** Operations
**Notes:** This is the primary proxy for false positive rate. If review_rate spikes, the operations team's manual review queue will overflow. A sustained spike without a corresponding fraud_block_rate increase is a signal of over-sensitive rules.

---

## Operational Metrics

### 3. `p99_latency_ms`
**Definition:** 99th percentile end-to-end evaluation latency in milliseconds.
**Target:** < 200ms
**Alert Threshold:** > 350ms (SLO breach)
**Window:** Rolling 1h
**Owner:** Engineering
**Notes:** The payment service has a 500ms timeout. At p99 > 350ms, there is risk of timeout-induced decisions. Latency spikes are most commonly caused by slow DB writes (audit log) or model loading. The `async_audit_log` feature flag mitigates the DB path.

---

### 4. `rule_hit_rates`
**Definition:** Per-rule fraction of evaluated transactions where the rule fired.
**Formula:** `rule_fires / total_evaluated` per rule ID
**Target:** No rule at 0% (dead rule) or > 50% (over-firing)
**Alert Threshold:** Any rule at 0% for 7 days → dead rule review; any rule > 30% for 24h → over-firing alert
**Window:** Rolling 7d
**Owner:** Fraud Risk
**Notes:** Dead rules waste CPU and confuse analysts. Over-firing rules dominate the score and may be suppressing the signal from more targeted rules. This metric enables risk analysts to proactively manage the rule portfolio without waiting for engineering escalation.

---

### 5. `score_percentiles` (p50, p90, p99)
**Definition:** Score distribution percentiles across all evaluated transactions.
**Window:** Rolling 24h
**Owner:** Engineering + Fraud Risk
**Notes:** The p50 should be near 10–20 for a healthy system (most transactions are low-risk). If p50 climbs toward 40, it may indicate a noisy new rule or ML model drift. If p99 drops below the block threshold, the model may be under-detecting. Track changes before and after rule updates or model version changes.

---

## Experiment Metrics

### 6. Per-variant `fraud_block_rate` and `review_rate`
**Definition:** The same primary metrics, computed separately per experiment variant.
**Purpose:** Determine if the treatment variant (e.g., new ML model) outperforms the control on the primary metric without degrading the guardrail metric.
**Graduation Criteria:**
- Minimum sample size: 10,000 transactions per variant
- Statistical significance: p < 0.05
- Minimum improvement on primary metric: +10%
- No regression on guardrail metrics (review_rate must not increase by > 5% relative)

---

## Metric Relationships

```
fraud_block_rate ↑ + review_rate stable → Improved detection ✓
fraud_block_rate ↑ + review_rate ↑      → Over-blocking (false positives) ✗
fraud_block_rate ↓ + review_rate ↓      → Under-detection ✗
fraud_block_rate ↓ + review_rate stable → Model degradation or rule gaps ✗
```

---

## Data Freshness

All metrics are computed on-demand from the `audit_log` table. There is no separate aggregation job. This means:
- Metrics are always fresh (no lag)
- Dashboard latency increases with data volume (consider periodic snapshotting for >1M records)
- The `metrics_snapshots` table is reserved for cached rollups at scale
