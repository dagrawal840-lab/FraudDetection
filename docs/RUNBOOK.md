# Operational Runbook
## Fraud Detection API

**On-Call Rotation:** fraud-engineering
**Escalation:** fraud-risk-team (rules), ml-platform (model issues)
**PagerDuty:** fraud-detection-api

---

## Common Incidents

### Incident: Fraud Rate Spike
**Symptoms:** `fraud_block_rate` > 5% in rolling 1h window
**Likely Cause:** New fraud vector, or a rule change that increased sensitivity
**Steps:**
1. Check if a rule was recently reloaded: `GET /v1/rules` and compare `version` field
2. Check rule_hit_rates in dashboard: `GET /v1/metrics/dashboard` — identify any rule with a sharp increase in hit rate
3. If a specific rule is over-firing, disable it in `config/rules.yaml` and call `PUT /v1/rules/reload`
4. If ML model appears to be the cause, disable via feature flag: set `ml_scoring_enabled.enabled: false` in `config/feature_flags.yaml` and restart (or call reload if implemented)
5. Page fraud risk analyst to confirm whether the spike reflects real fraud or false positives

---

### Incident: Review Queue Overload
**Symptoms:** `review_rate` > 8% sustained for 30+ minutes
**Likely Cause:** Threshold misconfiguration, new rule with high score_contribution, or ML score distribution shift
**Steps:**
1. Check `score_percentiles.p90` — if it has risen significantly, scores are being inflated
2. Identify over-firing rules via `rule_hit_rates` in dashboard
3. Raise the review threshold temporarily (config/rules.yaml `thresholds.review`) and reload
4. If ML is contributing high scores, check model version: `GET /v1/rules` (model_version in response)
5. If new model version was recently rolled out via A/B test, roll back by updating experiment traffic split

---

### Incident: Latency SLO Breach (p99 > 350ms)
**Symptoms:** `p99_latency_ms` > 350ms in rolling 1h
**Likely Cause:** DB bottleneck (audit log writes), model loading delay, high concurrency
**Steps:**
1. Check if `async_audit_log` feature flag is enabled: `GET /v1/rules` (flag state visible in health endpoint)
2. If synchronous audit log is the bottleneck, enable async flag: set `async_audit_log.enabled: true` and reload
3. Check DB connection pool: look for slow query logs in the database
4. If model loading is slow: verify `ml/artifacts/` — large model files slow cold starts
5. Horizontal scaling: spin up additional API instances behind the load balancer

---

### Incident: API Returns 500 Errors
**Symptoms:** HTTP 500 rate > 0.1% on POST /v1/transactions/evaluate
**Steps:**
1. Check logs for exception stack traces — most common causes:
   - `FileNotFoundError` on config/rules.yaml → file missing or wrong path in env var
   - `AttributeError` on model → model file corrupt or version mismatch
   - DB connection failure → check DATABASE_URL env var
2. For config file errors: verify `RULES_CONFIG_PATH`, `FEATURE_FLAGS_PATH` env vars
3. For model errors: re-run `python ml/train.py` to regenerate artifacts
4. For DB errors: if using SQLite, check disk space; if PostgreSQL, check connection string

---

## Routine Operations

### Adding a New Fraud Rule
1. Edit `config/rules.yaml` — add a new entry under `rules:`
2. Set `enabled: false` initially (shadow mode)
3. Call `PUT /v1/rules/reload` to load the new rule
4. Monitor `rule_hit_rates` for the new rule's ID — verify it fires on expected transactions
5. Set `enabled: true` and reload to activate
6. Commit the config change to git

### Updating a Rule Threshold
1. Edit `config/rules.yaml` — change the `threshold` value
2. Call `PUT /v1/rules/reload`
3. Monitor `review_rate` and `fraud_block_rate` for 30 minutes
4. Commit to git

### Rolling Back a Model Version
1. Identify the stable version: `GET /v1/rules` → check `model_version`
2. In `config/ab_experiments.yaml`, update the relevant experiment to 0% treatment weight
3. Restart the API (model_registry reloads on startup) OR
4. Use the `ml_scoring_enabled` feature flag to disable ML entirely as an emergency measure

### Disabling ML Scoring (Emergency)
1. Edit `config/feature_flags.yaml`: set `ml_scoring_enabled.enabled: false`
2. Restart the API (feature flags are loaded at startup; live reload is via the reload endpoint if configured)
3. System falls back to rule-only scoring
4. Re-enable once root cause is identified

---

## Key Endpoints Reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Service health + loaded model versions |
| `/v1/transactions/evaluate` | POST | Evaluate transaction (primary hot path) |
| `/v1/transactions/{id}/audit` | GET | Full audit trail for a transaction |
| `/v1/rules` | GET | Current rules config |
| `/v1/rules/reload` | PUT | Hot-reload rules from YAML |
| `/v1/experiments` | GET | All A/B experiments |
| `/v1/metrics/dashboard` | GET | KPI dashboard (1h/24h/7d) |
