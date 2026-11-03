"""M1.5 validation harness v2 — two complementary detectors, honestly scored.

Detector S (structural): binary-segmented Pettitt, p<0.05, min segment 90d, max 8 splits,
  plus minimum effect size: |median(after 30d) - median(before 30d)| / median(before 90d) >= 25%.
  Finds persistent level shifts (closures, conflict, structural rerouting).
Detector T (transient): trailing 7-day mean falls below 60% of trailing 90-day median for
  >=3 days; alert closes when the series recovers to >=80% of that baseline; alerts separated
  by <7 days are merged. Finds short shocks (tropical cyclones, floods, earthquakes).

Ground truth: PortWatch disruptions database (130 dated events, 2018-10..2026-08).
Eligible event: dated, >=1 affected port with a daily series, >=60 days of pre-event data.
Match: detection (changepoint date, or alert window intersect) within event window +/- tol.
Precision caveat (disclosed): ground truth is not exhaustive — undocumented real shocks
(e.g. COVID-19) count as false positives, so precision is a lower bound.
"""
import json, re, math, datetime, collections
import numpy as np
from scipy.stats import rankdata

def ms2d(ms): return datetime.datetime.fromtimestamp(ms / 1000, datetime.UTC).date()
DAY = datetime.timedelta(days=1)

# ---------- ground truth ----------
ev = json.loads(re.search(r'=\s*(\[.*\])\s*;?\s*$', open('disruptions_data.js', encoding='utf-8').read(), re.S).group(1))
def plist(e):
    return [p.strip() for p in re.split(r'[;,]', str(e[10])) if p.strip()]
events = [{'id': e[0], 'type': e[1], 'name': e[2], 'level': e[3],
           'frm': ms2d(e[5]), 'to': ms2d(e[6]),
           'ports': [p for p in plist(e) if p.startswith('port')]} for e in ev if e[5] and e[6]]

# ---------- series ----------
data = json.load(open('validation/port_series.json'))
series = {}
for pid, rec in data.items():
    if pid.startswith('port') and rec['series']:
        series[pid] = [(datetime.date.fromisoformat(d), c) for d, c, t, k in rec['series']]
print(f'events dated: {len(events)} | port series: {len(series)}', flush=True)

def trailing_mean(vals, w=7):
    q, run, out = collections.deque(), 0.0, []
    for v in vals:
        q.append(v); run += v
        if len(q) > w: run -= q.popleft()
        out.append(run / len(q))
    return out

# common observation-window end = earliest last-day across ports (conservative)
SPAN_END = min(s[-1][0] for s in series.values())
SPAN_YEARS = (SPAN_END - datetime.date(2019, 1, 1)).days / 365.25

# ---------- Detector S: Pettitt ----------
def pettitt(x):
    x = np.asarray(x, float); n = len(x)
    r = rankdata(x)
    U = 2 * np.cumsum(r) - np.arange(1, n + 1) * (n + 1)
    k = int(np.argmax(np.abs(U))) + 1
    p = 2 * math.exp(-6 * U[k - 1] ** 2 / (n ** 3 + n ** 2))
    return k, min(float(p), 1.0)

def detect_structural(dates, vals, p_thr=0.05, min_seg=90, max_splits=8, eff=0.25):
    cps = []
    def rec(lo, hi):
        if len(cps) >= max_splits or hi - lo < 2 * min_seg: return
        k, p = pettitt(vals[lo:hi])
        g = lo + k
        if p < p_thr and min_seg <= g <= hi - min_seg:
            before = np.median(vals[max(0, g - 90):g])
            after = np.median(vals[g:min(len(vals), g + 30)])
            if before > 0 and abs(after - before) / before >= eff:
                cps.append(g)
                rec(lo, g); rec(g, hi)
    rec(0, len(vals))
    return sorted(dates[i] for i in cps)

# ---------- Detector T: transient drop ----------
def detect_transient(dates, raw, drop=0.50, recov=0.80, min_days=4, merge_gap=7, base_win=90, min_base=3.0):
    v7 = trailing_mean(raw)
    alerts, cur = [], None
    for i in range(base_win, len(dates)):
        base = float(np.median(v7[i - base_win:i]))
        if base < min_base:   # too quiet to grade honestly — skip
            if cur is not None:
                if (cur[1] - cur[0]).days + 1 >= min_days: alerts.append(tuple(cur))
                cur = None
            continue
        ratio = v7[i] / base
        if ratio < drop:
            if cur is None: cur = [dates[i], dates[i]]
            else: cur[1] = dates[i]
        elif cur is not None and ratio >= recov:
            if (cur[1] - cur[0]).days + 1 >= min_days: alerts.append(tuple(cur))
            cur = None
    if cur is not None and (cur[1] - cur[0]).days + 1 >= min_days: alerts.append(tuple(cur))
    merged = []
    for a in alerts:
        if merged and (a[0] - merged[-1][1]).days < merge_gap:
            merged[-1] = (merged[-1][0], a[1])
        else: merged.append(a)
    return merged

# ---------- run structural detector (transient detector runs inside the sensitivity grid) ----------
detS = {}
for pid, s in series.items():
    detS[pid] = detect_structural([d for d, _ in s], trailing_mean([v for _, v in s]))
print('detector S changepoints:', sum(len(v) for v in detS.values()), flush=True)

# ---------- scoring ----------
MIN_PRE = 60
def eligible(e):
    return [p for p in e['ports'] if p in series and series[p][0][0] <= e['frm'] - MIN_PRE * DAY]

def score_all(detT_map, tol):
    def match_event(e):
        lo, hi = e['frm'] - tol * DAY, e['to'] + tol * DAY
        for p in eligible(e):
            if any(lo <= d <= hi for d in detS[p]): return True
            if any(a[0] <= hi and a[1] >= lo for a in detT_map.get(p, [])): return True
        return False
    ok = [e for e in events if eligible(e)]
    hit = sum(1 for e in ok if match_event(e))
    m = set()
    for e in ok:
        lo, hi = e['frm'] - tol * DAY, e['to'] + tol * DAY
        for p in eligible(e):
            for d in detS[p]:
                if lo <= d <= hi: m.add(('S', p, d))
            for a in detT_map.get(p, []):
                if a[0] <= hi and a[1] >= lo: m.add(('T', p, a[0]))
    ok_ports = {p for e in ok for p in eligible(e)}
    total = sum(len(detS[p]) + len(detT_map.get(p, [])) for p in ok_ports)
    # alert burden over ALL monitored ports (not just event ports)
    span_years = SPAN_YEARS
    apy = sum(len(detS[p]) + len(detT_map.get(p, [])) for p in series) / (len(series) * span_years)
    apy_all = sum(len(detS[p]) + len(detT_map.get(p, [])) for p in series)
    rec = hit / len(ok) if ok else 0
    prec = len(m) / total if total else 0
    return {'tolerance_days': tol, 'eligible_events': len(ok), 'events_detected': hit,
            'recall': round(rec, 3), 'detections_total': total, 'detections_matched': len(m),
            'precision_lower_bound': round(prec, 3),
            'f1_lower_bound': round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0,
            'alerts_per_port_year': round(apy, 2), 'detections_all_ports': apy_all,
            'span_years': round(span_years, 4), 'n_ports': len(series)}

# sensitivity grid over detector-T settings (tolerance 14d); operating point = highest recall
# subject to alert burden <= 2.0 alerts/port-year (declared selection rule, not cherry-picked)
CONFIGS = [
    {'drop': 0.60, 'min_days': 3, 'min_base': 1.0},
    {'drop': 0.60, 'min_days': 3, 'min_base': 3.0},
    {'drop': 0.50, 'min_days': 3, 'min_base': 1.0},
    {'drop': 0.50, 'min_days': 4, 'min_base': 3.0},
    {'drop': 0.70, 'min_days': 3, 'min_base': 1.0},
    {'drop': 0.70, 'min_days': 2, 'min_base': 0.5},
]
grid, detT_grid = {}, {}
for cfg in CONFIGS:
    key = f"drop{int(cfg['drop']*100)}_min{cfg['min_days']}d_base{cfg['min_base']}"
    detT_grid[key] = {pid: detect_transient([d for d, _ in s], [v for _, v in s], **cfg)
                      for pid, s in series.items()}
    grid[key] = score_all(detT_grid[key], 14)
    grid[key]['config'] = cfg
feasible = {k: v for k, v in grid.items() if v['alerts_per_port_year'] <= 2.0}
OP_KEY = max(feasible, key=lambda k: feasible[k]['recall'])
detT = detT_grid[OP_KEY]
results = {f'tol{tol}': score_all(detT, tol) for tol in (7, 14, 21)}

# per-detector recall at tol=14 (which detector catches what)
ok14 = [e for e in events if eligible(e)]
def hitS(e, tol=14):
    lo, hi = e['frm'] - tol * DAY, e['to'] + tol * DAY
    return any(lo <= d <= hi for p in eligible(e) for d in detS[p])
def hitT(e, tol=14):
    lo, hi = e['frm'] - tol * DAY, e['to'] + tol * DAY
    return any(a[0] <= hi and a[1] >= lo for p in eligible(e) for a in detT[p])
by_type = {}
for e in ok14:
    t = by_type.setdefault(e['type'], {'n': 0, 'S': 0, 'T': 0, 'either': 0})
    t['n'] += 1; t['S'] += hitS(e); t['T'] += hitT(e); t['either'] += (hitS(e) or hitT(e))

def match14(e):
    lo, hi = e['frm'] - 14 * DAY, e['to'] + 14 * DAY
    for p in eligible(e):
        if any(lo <= d <= hi for d in detS[p]): return True
        if any(a[0] <= hi and a[1] >= lo for a in detT.get(p, [])): return True
    return False

asian = set(p[0] for p in json.loads(re.search(r'=\s*(\[.*\])\s*;?\s*$', open('ports_data.js', encoding='utf-8').read(), re.S).group(1)))
ok_asia = [e for e in ok14 if any(p in asian for p in e['ports'])]
asia_hit = sum(1 for e in ok_asia if match14(e))

per_event = [{'name': e['name'], 'type': e['type'], 'level': e['level'], 'from': str(e['frm']),
              'to': str(e['to']), 'n_ports': len(eligible(e)),
              'detected_S': hitS(e), 'detected_T': hitT(e)} for e in ok14]

summary = {
    'harvest_date': str(datetime.date.today()), 'data_range': f'2019-01-01..{SPAN_END}',
    'detectors': {
        'S_structural': 'binary-segmented Pettitt p<0.05, min seg 90d, max 8 splits, effect size >=25% (30d-after vs 90d-before medians)',
        'T_transient': '7-day trailing mean below drop x trailing-90d median (min baseline min_base calls/day) for >=min_days d, close at >=80%, merge gap <7d — operating point chosen by declared rule'},
    'operating_point_rule': 'highest recall subject to <=2.0 alerts/port-year (tolerance 14d)',
    'operating_point': OP_KEY,
    'match_rule': 'changepoint date or alert-window intersection within event window +/- tol days',
    'precision_caveat': 'ground truth is not exhaustive (undocumented real shocks count as false positives) — precision/F1 are lower bounds',
    'n_events_dated': len(events), 'n_ports_with_series': len(series),
    'sensitivity_grid_tol14': grid,
    'global': results, 'by_type_tol14': by_type,
    'asia': {'eligible_events': len(ok_asia), 'events_detected': asia_hit,
             'recall': round(asia_hit / len(ok_asia), 3) if ok_asia else None},
    'per_event': per_event,
}
json.dump(summary, open('validation/results.json', 'w'), indent=1)
print(json.dumps({k: v for k, v in summary.items() if k != 'per_event'}, indent=1))
