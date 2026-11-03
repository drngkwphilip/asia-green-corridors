"""Harvest daily port-call series, threaded. Single run, writes validation/port_series.json."""
import json, re, time, os
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

ARC = 'https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/'
Q = ARC + 'Daily_Ports_Data/FeatureServer/0/query'

ev = json.loads(re.search(r'=\s*(\[.*\])\s*;?\s*$', open('disruptions_data.js', encoding='utf-8').read(), re.S).group(1))
dated = [e for e in ev if e[5] and e[6]]
def plist(e):
    return [p.strip() for p in re.split(r'[;,]', str(e[10])) if p.strip()]
ports = sorted(set(p for e in dated for p in plist(e)))
print(f'{len(ports)} ports to harvest', flush=True)

def fetch(pid):
    rows, offset = [], 0
    for attempt in range(3):
        try:
            while True:
                r = requests.get(Q, params={
                    'where': f"portid='{pid}'",
                    'outFields': 'date,portname,portcalls,portcalls_tanker,portcalls_container',
                    'orderByFields': 'date ASC',
                    'resultRecordCount': 1000, 'resultOffset': offset, 'f': 'json'}, timeout=45)
                feats = r.json().get('features', [])
                rows += [f['attributes'] for f in feats]
                if len(feats) < 1000:
                    break
                offset += 1000
            return pid, {
                'portname': rows[0]['portname'] if rows else pid,
                'series': [[x['date'], x['portcalls'] or 0, x['portcalls_tanker'] or 0, x['portcalls_container'] or 0] for x in rows],
            }, None
        except Exception as ex:
            time.sleep(1.5)
            err = str(ex)
    return pid, None, err

out, failed = {}, []
t0 = time.time()
with ThreadPoolExecutor(max_workers=14) as ex:
    futs = {ex.submit(fetch, p): p for p in ports}
    for i, fut in enumerate(as_completed(futs)):
        pid, data, err = fut.result()
        if data is not None:
            out[pid] = data
        else:
            failed.append(pid)
        if (i + 1) % 25 == 0 or i + 1 == len(ports):
            print(f'[{i+1}/{len(ports)}] {time.time()-t0:.0f}s', flush=True)

os.makedirs('validation', exist_ok=True)
json.dump(out, open('validation/port_series.json', 'w'))
empty = [p for p, v in out.items() if not v['series']]
print('saved', len(out), 'ports;', len(failed), 'failed:', failed[:8])
print('ports with 0 days:', len(empty), empty[:8])
