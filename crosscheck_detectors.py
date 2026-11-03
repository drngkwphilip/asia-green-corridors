"""Cross-check: Python detectors vs the shipped JS detectors, on the six corridor hubs.
Extracts the detector functions verbatim from dashboard.html and evals them in Node."""
import json, re, subprocess, datetime, collections
import numpy as np
from scipy.stats import rankdata
import math

html = open('dashboard.html', encoding='utf-8').read()
script = re.findall(r'<script>(.*?)</script>', html, re.S)[0]
start = script.find('function trail7')
end = script.find('function isoDays')
detector_js = script[start:end]

hub = json.loads(re.search(r'window\.HUBSERIES = (\{.*\});', open('hubseries_data.js', encoding='utf-8').read(), re.S).group(1))

# ---- JS side (shipped code, verbatim) ----
js_test = detector_js + """
const fs = require('fs');
const hub = JSON.parse(fs.readFileSync('validation/_hub_for_js.json', 'utf8'));
const out = {};
for (const pid of Object.keys(hub)) {
  const dates = hub[pid].series.map(r => r[0]);
  const raw = hub[pid].series.map(r => r[1]);
  out[pid] = { S: detectS(dates, trail7(raw)).map(c => c.date),
               T: detectT(dates, raw).map(a => [a.frm, a.to]) };
}
console.log(JSON.stringify(out));
"""
json.dump(hub, open('validation/_hub_for_js.json', 'w'))
open('validation/_jsdet.js', 'w').write(js_test)
js_out = json.loads(subprocess.run(['node', 'validation/_jsdet.js'], capture_output=True, text=True, check=True).stdout)

# ---- Python side (harness, operating point config) ----
def trailing7(vals):
    q, run, out = collections.deque(), 0.0, []
    for v in vals:
        q.append(v); run += v
        if len(q) > 7: run -= q.popleft()
        out.append(run / len(q))
    return out

def pettitt(x):
    x = np.asarray(x, float); n = len(x)
    r = rankdata(x)
    U = 2 * np.cumsum(r) - np.arange(1, n + 1) * (n + 1)
    k = int(np.argmax(np.abs(U))) + 1
    p = 2 * math.exp(-6 * U[k - 1] ** 2 / (n ** 3 + n ** 2))
    return k, min(float(p), 1.0)

def detectS(dates, v7):
    cps = []
    def rec(lo, hi):
        if len(cps) >= 8 or hi - lo < 180: return
        k, p = pettitt(v7[lo:hi]); g = lo + k
        if p < 0.05 and g - lo >= 90 and hi - g >= 90:
            before = float(np.median(v7[max(0, g - 90):g]))
            after = float(np.median(v7[g:min(len(v7), g + 30)]))
            if before > 0 and abs(after - before) / before >= 0.25:
                cps.append(dates[g]); rec(lo, g); rec(g, hi)
    rec(0, len(v7))
    return sorted(cps)

def detectT(dates, raw):
    v7 = trailing7(raw); alerts = []; cur = None
    for i in range(90, len(dates)):
        base = float(np.median(v7[i - 90:i]))
        if base < 1.0:
            if cur: alerts.append(cur); cur = None
            continue
        ratio = v7[i] / base
        if ratio < 0.6:
            if cur is None: cur = [dates[i], dates[i]]
            else: cur[1] = dates[i]
        elif cur is not None and ratio >= 0.8:
            alerts.append(cur); cur = None
    if cur: alerts.append(cur)
    alerts = [a for a in alerts if (datetime.date.fromisoformat(a[1]) - datetime.date.fromisoformat(a[0])).days + 1 >= 3]
    merged = []
    for a in alerts:
        if merged and (datetime.date.fromisoformat(a[0]) - datetime.date.fromisoformat(merged[-1][1])).days < 7:
            merged[-1][1] = a[1]
        else: merged.append(list(a))
    return [tuple(a) for a in merged]

print(f"{'hub':12} {'S py':>4} {'S js':>4} {'T py':>4} {'T js':>4}  match")
allok = True
for pid, rec in hub.items():
    dates = [d for d, _ in rec['series']]; raw = [v for _, v in rec['series']]
    pS, pT = detectS(dates, trailing7(raw)), detectT(dates, raw)
    jS, jT = js_out[pid]['S'], [tuple(x) for x in js_out[pid]['T']]
    ok = pS == sorted(jS) and pT == jT
    allok &= ok
    print(f"{rec['name']:12} {len(pS):>4} {len(jS):>4} {len(pT):>4} {len(jT):>4}  {'IDENTICAL' if ok else 'DIFF'}")
    if not ok:
        print('  py S:', pS); print('  js S:', sorted(jS))
        print('  py T:', pT); print('  js T:', jT)
print('ALL IDENTICAL' if allok else 'MISMATCHES FOUND')
