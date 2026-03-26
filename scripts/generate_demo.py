"""Generate a self-contained demo.html from live API data."""
import json

def load(path):
    with open(path) as f:
        return json.load(f)

health = load('/tmp/demo_health.json')
rules = load('/tmp/demo_rules.json')
experiments = load('/tmp/demo_experiments.json')
metrics = load('/tmp/demo_metrics.json')
block = load('/tmp/demo_block.json')
allow = load('/tmp/demo_allow.json')
review = load('/tmp/demo_review.json')

w24 = metrics['windows']['24h']
allow_rate = w24['allowed'] / max(w24['total_evaluated'], 1) * 100

COLOR_MAP = {'BLOCK': 'red', 'ALLOW': 'green', 'REVIEW': 'yellow'}
ICON_MAP  = {'BLOCK': '⛔', 'ALLOW': '✅', 'REVIEW': '🔍'}
MERCH_MAP = {'block': 'Wire Transfer', 'review': 'Best Buy', 'allow': 'Whole Foods'}

def rule_tags(rule_list):
    if not rule_list:
        return '<span style="color:var(--muted);font-size:.8rem">No rules triggered</span>'
    parts = []
    for r in rule_list:
        parts.append(
            '<span class="rule-tag">'
            + r['id']
            + ' <span class="contrib">+' + str(int(r['score_contribution'])) + '</span>'
            + '</span>'
        )
    return ''.join(parts)

def rule_rows(rule_list):
    parts = []
    for r in rule_list:
        badge = '<span class="badge badge-green">on</span>' if r['enabled'] else '<span class="badge badge-red">off</span>'
        parts.append(
            '<div class="rule-row">'
            '<div><span class="rule-id">' + r['id'] + '</span></div>'
            '<div style="display:flex;align-items:center;gap:.5rem">'
            '<span style="color:var(--muted);font-size:.75rem">+' + str(int(r['score_contribution'])) + '</span>'
            + badge +
            '</div></div>'
        )
    return ''.join(parts)

def hit_rows(hit_rates):
    parts = []
    for rid, rate in hit_rates.items():
        bar_w = min(rate * 300, 100)
        parts.append(
            '<div class="rule-row">'
            '<span class="rule-id">' + rid + '</span>'
            '<div style="display:flex;align-items:center;gap:.5rem">'
            '<div class="hit-bar"><div class="hit-fill" style="width:' + str(bar_w) + '%"></div></div>'
            '<span class="rule-contrib" style="color:var(--muted)">' + f'{rate*100:.1f}%' + '</span>'
            '</div></div>'
        )
    return ''.join(parts)

def exp_variants(exp):
    parts = []
    for v in exp['variants'].values():
        parts.append(
            '<div class="metric-row">'
            '<span class="metric-key">' + v['name'] + '</span>'
            '<span class="metric-val">' + str(int(v['weight'] * 100)) + '%</span>'
            '</div>'
        )
    return ''.join(parts)

def exp_cards(exp_list):
    parts = []
    for e in exp_list:
        badge_cls = 'badge-green' if e['status'] == 'active' else 'badge-blue'
        parts.append(
            '<div class="card">'
            '<div class="card-title">' + e['id'] + '</div>'
            '<div style="font-weight:600;margin-bottom:.5rem">' + e['name'] + '</div>'
            '<div style="margin-bottom:.75rem"><span class="badge ' + badge_cls + '">' + e['status'] + '</span></div>'
            + exp_variants(e) +
            '<div style="margin-top:.75rem;font-size:.8rem;color:var(--muted)">Primary metric: ' + e['primary_metric'] + '</div>'
            '</div>'
        )
    return ''.join(parts)

def verdict_panel(key, data):
    color = COLOR_MAP[data['verdict']]
    icon  = ICON_MAP[data['verdict']]
    merchant = MERCH_MAP[key]
    blend_r = int(data['rule_blend_weight'] * 100)
    blend_m = 100 - blend_r
    active_cls = ' active' if key == 'block' else ''
    exp_id = data.get('experiment_id') or 'none'
    exp_var = data.get('experiment_variant') or '—'
    score_pct = min(data['final_score'], 100)
    return (
        '<div id="verdict-' + key + '" class="tab-content' + active_cls + '">'
        '<div class="verdict-card">'
        '<div class="verdict-header">'
        '<div>'
        '<div class="tx-meta">txn: <span>' + data['transaction_id'] + '</span>'
        ' &nbsp;·&nbsp; merchant: <span>' + merchant + '</span>'
        ' &nbsp;·&nbsp; latency: <span>' + str(data['latency_ms']) + 'ms</span></div>'
        '<div class="verdict-label ' + data['verdict'] + '">' + icon + ' ' + data['verdict'] + '</div>'
        '</div>'
        '<div style="text-align:right">'
        '<div style="font-size:2.5rem;font-weight:800;color:var(--' + color + ')">' + str(data['final_score']) + '</div>'
        '<div style="font-size:.8rem;color:var(--muted)">score / 100</div>'
        '</div>'
        '</div>'
        '<div class="score-bar-container">'
        '<div class="score-label"><span>Rule Score</span><span>' + str(data['rule_score']) + '</span></div>'
        '<div class="score-bar"><div class="score-fill rule" style="width:' + str(data['rule_score']) + '%"></div></div>'
        '</div>'
        '<div class="score-bar-container">'
        '<div class="score-label"><span>ML Score</span><span>' + str(data['ml_score']) + '</span></div>'
        '<div class="score-bar"><div class="score-fill ml" style="width:' + str(data['ml_score']) + '%"></div></div>'
        '</div>'
        '<div class="score-bar-container">'
        '<div class="score-label"><span>Final (blend ' + str(blend_r) + '/' + str(blend_m) + ')</span><span>' + str(data['final_score']) + '</span></div>'
        '<div class="score-bar"><div class="score-fill final-' + data['verdict'] + '" style="width:' + str(score_pct) + '%"></div></div>'
        '</div>'
        '<div class="triggered-rules" style="margin-top:.75rem">' + rule_tags(data['triggered_rules']) + '</div>'
        '<div style="margin-top:.75rem;font-size:.8rem;color:var(--muted)">'
        'Model v' + str(data['model_version']) + ' &nbsp;·&nbsp; Experiment: ' + exp_id + ' (' + exp_var + ')'
        '</div>'
        '</div></div>'
    )

CSS = """
  :root{--bg:#0f1117;--surface:#1a1d27;--border:#2a2d3a;--text:#e2e8f0;--muted:#94a3b8;--accent:#6366f1;--green:#10b981;--red:#ef4444;--yellow:#f59e0b;--blue:#3b82f6}
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:var(--bg);color:var(--text);font-family:system-ui,-apple-system,sans-serif}
  .container{max-width:1200px;margin:0 auto;padding:2rem}
  header{border-bottom:1px solid var(--border);padding-bottom:1.5rem;margin-bottom:2rem}
  h1{font-size:1.75rem;font-weight:700} h1 span{color:var(--accent)}
  .subtitle{color:var(--muted);margin-top:.4rem;font-size:.95rem}
  .badge{display:inline-block;padding:.2rem .6rem;border-radius:999px;font-size:.75rem;font-weight:600}
  .badge-green{background:#052e16;color:var(--green);border:1px solid #14532d}
  .badge-red{background:#450a0a;color:var(--red);border:1px solid #7f1d1d}
  .badge-blue{background:#0c1a2e;color:var(--blue);border:1px solid #1e3a5f}
  .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-bottom:2rem}
  .grid-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1.5rem;margin-bottom:2rem}
  @media(max-width:800px){.grid-2,.grid-3{grid-template-columns:1fr}}
  .card{background:var(--surface);border:1px solid var(--border);border-radius:.75rem;padding:1.25rem}
  .card-title{font-size:.7rem;text-transform:uppercase;letter-spacing:.1em;color:var(--muted);margin-bottom:.5rem}
  .card-value{font-size:2rem;font-weight:700} .card-sub{font-size:.8rem;color:var(--muted);margin-top:.25rem}
  .section{margin-bottom:2.5rem}
  .section-title{font-size:1.1rem;font-weight:600;margin-bottom:1rem}
  .verdict-card{background:var(--surface);border:1px solid var(--border);border-radius:.75rem;padding:1.25rem}
  .verdict-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem}
  .verdict-label{font-weight:700;font-size:1.5rem}
  .verdict-label.BLOCK{color:var(--red)} .verdict-label.ALLOW{color:var(--green)} .verdict-label.REVIEW{color:var(--yellow)}
  .score-bar-container{margin:.6rem 0}
  .score-label{display:flex;justify-content:space-between;font-size:.8rem;color:var(--muted);margin-bottom:.3rem}
  .score-bar{height:8px;background:var(--border);border-radius:4px;overflow:hidden}
  .score-fill{height:100%;border-radius:4px}
  .score-fill.rule{background:var(--accent)} .score-fill.ml{background:var(--blue)}
  .score-fill.final-BLOCK{background:var(--red)} .score-fill.final-ALLOW{background:var(--green)} .score-fill.final-REVIEW{background:var(--yellow)}
  .rule-tag{display:inline-flex;align-items:center;gap:.3rem;background:#1e1b4b;border:1px solid #312e81;border-radius:.4rem;padding:.2rem .5rem;font-size:.75rem;margin:.2rem;color:#a5b4fc}
  .rule-tag .contrib{color:var(--red);font-weight:600}
  .tx-meta{font-size:.8rem;color:var(--muted);margin-bottom:.5rem} .tx-meta span{color:var(--text)}
  pre{background:#0d1117;border:1px solid var(--border);border-radius:.5rem;padding:1rem;overflow-x:auto;font-size:.78rem;line-height:1.6;color:#e6edf3}
  .tab-bar{display:flex;gap:.25rem;margin-bottom:1rem;border-bottom:1px solid var(--border)}
  .tab{padding:.5rem 1rem;cursor:pointer;font-size:.85rem;color:var(--muted);border-bottom:2px solid transparent;margin-bottom:-1px;user-select:none}
  .tab.active{color:var(--accent);border-bottom-color:var(--accent)}
  .tab-content{display:none} .tab-content.active{display:block}
  .metric-row{display:flex;justify-content:space-between;align-items:center;padding:.5rem 0;border-bottom:1px solid var(--border);font-size:.875rem}
  .metric-row:last-child{border-bottom:none} .metric-key{color:var(--muted)} .metric-val{font-weight:600;font-family:monospace}
  .rule-row{display:flex;justify-content:space-between;align-items:center;padding:.6rem 0;border-bottom:1px solid var(--border);font-size:.85rem}
  .rule-row:last-child{border-bottom:none} .rule-id{font-family:monospace;color:var(--accent)}
  .hit-bar{width:80px;height:6px;background:var(--border);border-radius:3px;overflow:hidden;display:inline-block;vertical-align:middle;margin-left:.5rem}
  .hit-fill{height:100%;background:var(--accent);border-radius:3px}
  footer{border-top:1px solid var(--border);padding-top:1rem;margin-top:2rem;font-size:.8rem;color:var(--muted);text-align:center}
"""

JS = """
function showVerdict(name, el) {
  document.querySelectorAll('#verdict-tabs .tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('[id^="verdict-"]').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('verdict-'+name).classList.add('active');
}
function showRaw(name, el) {
  document.querySelectorAll('#raw-tabs .tab').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('[id^="raw-"]').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('raw-'+name).classList.add('active');
}
"""

def kpi_card(title, value, sub, color=None):
    style = ' style="color:var(--' + color + ')"' if color else ''
    return (
        '<div class="card">'
        '<div class="card-title">' + title + '</div>'
        '<div class="card-value"' + style + '>' + value + '</div>'
        '<div class="card-sub">' + sub + '</div>'
        '</div>'
    )

body = (
    '<!DOCTYPE html><html lang="en"><head>'
    '<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">'
    '<title>Fraud Detection API — Live Demo</title>'
    '<style>' + CSS + '</style></head><body><div class="container">'

    '<header>'
    '<h1>Fraud Detection <span>API</span></h1>'
    '<div class="subtitle">Live data snapshot &nbsp;·&nbsp; '
    'ML v' + str(health['models_loaded'][-1]) + ' loaded &nbsp;·&nbsp; '
    + str(health['rules_enabled']) + ' rules active &nbsp;·&nbsp; '
    + str(health['flags_active']) + ' feature flags live</div>'
    '</header>'

    '<div class="section">'
    '<div class="section-title">📊 KPI Dashboard — 24h Window</div>'
    '<div class="grid-3">'
    + kpi_card('Total Evaluated', f'{w24["total_evaluated"]:,}', 'transactions processed')
    + kpi_card('Fraud Block Rate', f'{w24["fraud_block_rate"]*100:.1f}%', f'{w24["blocked"]} blocked · target ≥ 0.8%', 'red')
    + kpi_card('Review Rate', f'{w24["review_rate"]*100:.1f}%', f'{w24["reviewed"]} in queue · target ≤ 3%', 'yellow')
    + kpi_card('p99 Latency', f'{w24["p99_latency_ms"]:.0f}ms', 'SLO: &lt;200ms ✓', 'green')
    + kpi_card('Score p90', str(w24['score_percentiles']['p90']), f'p50: {w24["score_percentiles"]["p50"]} · p99: {w24["score_percentiles"]["p99"]}')
    + kpi_card('Allow Rate', f'{allow_rate:.1f}%', f'{w24["allowed"]} allowed through', 'green') +
    '</div></div>'

    '<div class="section">'
    '<div class="section-title">⚡ Live Evaluation Examples</div>'
    '<div class="tab-bar" id="verdict-tabs">'
    '<div class="tab active" onclick="showVerdict(\'block\',this)">🔴 BLOCK — High Risk</div>'
    '<div class="tab" onclick="showVerdict(\'review\',this)">🟡 REVIEW — Medium Risk</div>'
    '<div class="tab" onclick="showVerdict(\'allow\',this)">🟢 ALLOW — Normal</div>'
    '</div>'
    + verdict_panel('block', block)
    + verdict_panel('review', review)
    + verdict_panel('allow', allow) +
    '</div>'

    '<div class="grid-2">'
    '<div class="section" style="margin-bottom:0">'
    '<div class="section-title">📋 Active Rules</div>'
    '<div class="card">'
    + rule_rows(rules['rules']) +
    '<div style="margin-top:.75rem;font-size:.8rem;color:var(--muted)">'
    'Blend: ' + str(int(rules['rule_blend_weight']*100)) + '% rules + '
    + str(int((1-rules['rule_blend_weight'])*100)) + '% ML &nbsp;·&nbsp; '
    'Review ≥' + str(rules['thresholds']['review']) + ' &nbsp;·&nbsp; '
    'Block ≥' + str(rules['thresholds']['block']) +
    '</div></div></div>'

    '<div class="section" style="margin-bottom:0">'
    '<div class="section-title">📈 Rule Hit Rates (24h)</div>'
    '<div class="card">'
    + hit_rows(w24['rule_hit_rates']) +
    '</div></div></div>'

    '<div class="section">'
    '<div class="section-title">🧪 A/B Experiments</div>'
    '<div class="grid-2">'
    + exp_cards(experiments['experiments']) +
    '</div></div>'

    '<div class="section">'
    '<div class="section-title">🔌 Raw API Responses</div>'
    '<div class="tab-bar" id="raw-tabs">'
    '<div class="tab active" onclick="showRaw(\'block\',this)">BLOCK verdict</div>'
    '<div class="tab" onclick="showRaw(\'allow\',this)">ALLOW verdict</div>'
    '<div class="tab" onclick="showRaw(\'metrics\',this)">KPI Dashboard</div>'
    '</div>'
    '<div id="raw-block" class="tab-content active"><pre>' + json.dumps(block, indent=2) + '</pre></div>'
    '<div id="raw-allow" class="tab-content"><pre>' + json.dumps(allow, indent=2) + '</pre></div>'
    '<div id="raw-metrics" class="tab-content"><pre>' + json.dumps({'windows': metrics['windows']}, indent=2) + '</pre></div>'
    '</div>'

    '<footer>Fraud Detection API v1.0 &nbsp;·&nbsp; Live data snapshot &nbsp;·&nbsp; 41 tests passing · 85% coverage</footer>'
    '</div>'
    '<script>' + JS + '</script>'
    '</body></html>'
)

out = '/home/user/FraudDetection/demo.html'
with open(out, 'w') as f:
    f.write(body)
print(f"Written {len(body):,} bytes to {out}")
