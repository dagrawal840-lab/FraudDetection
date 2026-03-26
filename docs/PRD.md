# Product Requirements Document
## Fraud Detection API — v1.0

**Status:** Launched
**Author:** Product
**Last Updated:** 2026-03-25
**Stakeholders:** Fraud Risk, Engineering, Operations, Compliance, Finance

---

## 1. Problem Statement

### Background
Our payments platform processes ~500K transactions per day. The current fraud detection system is a static rule set maintained in a spreadsheet by the risk team and deployed via a monthly engineering sprint cycle. This creates two compounding problems:

1. **Slow response to new fraud patterns.** By the time a new rule is deployed, the fraud vector has often shifted. The average response time is 18 days.
2. **High false positive rate.** Static thresholds don't account for user behavioral baselines. Our current false positive rate is 2.1%, which is generating ~$320K/month in unnecessary chargebacks and customer service costs.

### Opportunity
A hybrid detection system — one that combines configurable rules with ML-based anomaly scoring — can:
- Cut response time to new fraud patterns from 18 days to <1 hour (via hot-reloadable rules)
- Reduce false positives by 40-60% by incorporating per-user behavioral baselines
- Enable safe, data-driven rollout of new detection models via A/B testing

---

## 2. Goals

### Primary Goals
- Detect fraudulent transactions with a fraud block rate ≥ 0.8% (vs. 0.6% baseline)
- Reduce false positive rate from 2.1% to ≤ 1.2%
- Enable risk analysts to deploy new/updated rules within 1 hour (no code deploy)
- Maintain p99 decision latency ≤ 200ms

### Secondary Goals
- Provide full decision explainability for regulatory audits (PCI-DSS, SOC2)
- Enable A/B testing of new ML models with <5% traffic risk exposure
- Surface KPI metrics for PM and ops review without requiring data engineering

---

## 3. Non-Goals (v1.0)

- **Real-time streaming:** v1.0 is a synchronous request/response API. Event streaming (Kafka) is out of scope.
- **Device fingerprinting:** The API accepts `is_new_device` as a pre-computed boolean. The device fingerprinting service is a separate system.
- **User notification:** Sending fraud alerts to end users is handled by the notification service, not this API.
- **Manual review queue UI:** The REVIEW verdict signals the review queue; the queue management UI is out of scope.
- **Model training pipeline:** v1.0 uses a script (`ml/train.py`). Automated MLOps pipeline is v2 scope.

---

## 4. User Stories

### Persona 1: Fraud Analyst (Rosa)
> *"I need to respond to a new fraud pattern within the hour, not in two weeks."*

- **As** a fraud analyst, **I want to** edit a YAML config to add/modify a fraud rule, **so that** the change is live without waiting for a sprint.
- **As** a fraud analyst, **I want to** see which rules fired for a blocked transaction, **so that** I can investigate false positives without needing engineering support.
- **As** a fraud analyst, **I want to** see per-rule fire rates in a dashboard, **so that** I can identify rules that never fire (dead rules) or fire too frequently (over-tuned).

### Persona 2: On-Call Engineer (Marcus)
> *"I need to understand what happened during a fraud spike and roll back if needed."*

- **As** an on-call engineer, **I want to** reload rules without restarting the server, **so that** I can respond to incidents without downtime.
- **As** an on-call engineer, **I want to** disable a feature flag instantly, **so that** I can kill a misbehaving ML model without a deploy.
- **As** an on-call engineer, **I want to** query the audit log for a transaction, **so that** I can reconstruct exactly why a decision was made.

### Persona 3: Downstream API Consumer (payment service)
> *"I need a verdict in under 200ms so I don't block the checkout flow."*

- **As** a payment service, **I want to** send a transaction and get a ALLOW/REVIEW/BLOCK verdict, **so that** I can decide whether to proceed, queue for review, or decline in real time.
- **As** a payment service, **I want to** receive the triggered rules in the response, **so that** I can display a generic decline reason to the user if needed.

---

## 5. Feature Specifications

### 5.1 Rule Engine
- Rules defined in `config/rules.yaml` — version-controlled, human-readable
- Each rule has: id, description, field, operator, threshold, score_contribution, enabled flag, owner
- Supported operators: `gt`, `lt`, `gte`, `lte`, `eq`, `neq`, `between`, `in`
- Rules are additive: multiple firing rules accumulate score (capped at 100)
- `PUT /v1/rules/reload` applies changes live without restart
- Every rule has an `owner` field to identify the accountable team

### 5.2 ML Anomaly Scoring
- Isolation Forest trained on labeled transaction features
- Score normalized to 0–100 (100 = most anomalous)
- Blended with rule score: `final = (rule_weight × rule_score) + ((1-rule_weight) × ml_score)`
- ML scoring gated by `ml_scoring_enabled` feature flag — instant kill switch
- Model version selectable per A/B experiment; default to latest

### 5.3 Verdict Thresholds
| Score Range | Verdict | Action |
|---|---|---|
| 0–39 | ALLOW | Transaction proceeds |
| 40–69 | REVIEW | Queue for human review |
| 70–100 | BLOCK | Transaction declined |

Thresholds are configurable in `config/rules.yaml` under `thresholds`.

### 5.4 Feature Flags
- Flags defined in `config/feature_flags.yaml`
- Each flag has rollout_percentage (0–100) and enabled toggle
- Assignment is deterministic per user_id — same user always gets same flag state
- Flags can be toggled without a restart (via config edit + reload)

### 5.5 A/B Testing
- Experiments defined in `config/ab_experiments.yaml`
- Each experiment has control and treatment variants with configurable traffic weights
- Assignments are deterministic per (user_id, experiment_id)
- Every evaluation is tagged with experiment_id and variant in the audit log
- `GET /v1/metrics/dashboard` shows per-variant KPIs for graduation decisions

### 5.6 Audit Log
- Every evaluation produces an immutable record in the `audit_log` table
- Fields: event_id, timestamp, transaction_id, user_id, verdict, all scores, triggered rules, experiment info, latency
- Retained indefinitely (configurable in prod via DB TTL policy)
- `GET /v1/transactions/{id}/audit` exposes the full trail per transaction

### 5.7 KPI Dashboard
- `GET /v1/metrics/dashboard` returns metrics across 1h, 24h, 7d windows
- No separate data pipeline required — aggregated from audit log in real time

---

## 6. Launch Plan

### Phase 0: Shadow Mode (Week 1)
- Deploy API with `ml_scoring_enabled` flag at 0%
- Route 100% of transactions through but do not act on verdicts
- Monitor latency SLO and error rates

### Phase 1: Soft Launch (Week 2)
- Enable ML scoring at 20% via feature flag
- Monitor fraud_block_rate and review_rate for anomalies
- Rule-only mode remains for 80% of traffic as control

### Phase 2: Gradual Rollout (Weeks 3–4)
- Increase ML flag rollout: 20% → 50% → 100%
- Gate each step on: fraud_block_rate stable, p99 latency < 200ms, review_rate not spiking

### Phase 3: GA (Week 5)
- 100% rollout
- Launch `exp_ml_model_v2` A/B experiment at 20% treatment
- Begin training and evaluating model v2

---

## 7. Success Metrics

| Metric | Baseline | Target | Owner |
|---|---|---|---|
| Fraud block rate | 0.6% | ≥ 0.8% | Fraud Risk |
| False positive rate | 2.1% | ≤ 1.2% | Fraud Risk |
| p99 decision latency | N/A (new) | < 200ms | Engineering |
| Rule deployment time | 18 days | < 1 hour | Risk Ops |
| Analyst investigation time | 45 min | < 10 min | Risk Ops |

---

## 8. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| ML model creates new false positives | Medium | High | Gradual rollout via feature flag; kill switch |
| Rules YAML misconfiguration causes outage | Low | High | Schema validation on load; reload returns error on invalid config |
| Latency regression under load | Low | High | Shadow mode performance testing before launch |
| Regulatory audit of ML decision | Medium | Medium | Full explainability payload + audit log |
| Fraud pattern shift post-launch | High | Medium | Hot-reloadable rules; analyst can update within 1 hour |
