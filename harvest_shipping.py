"""Harvest Climate TRACE v7 international-shipping sources (Asian subset) -> shipping_data.js."""
import json
import os
import time
import urllib.request

ASIA = set('CHN HKG MAC TWN JPN KOR PRK MNG SGP MYS IDN THA VNM PHL MMR KHM LAO BRN TLS '
           'IND PAK BGD LKA NPL BTN MDV KAZ UZB TKM KGZ TJK SAU ARE QAT KWT BHR OMN YEM '
           'IRQ IRN JOR ISR LBN SYR TUR GEO ARM AZE PNG RUS'.split())

ship_all, off, pages = [], 0, 0
while True:
    url = f'https://api.climatetrace.org/v7/sources?sectors=transportation&limit=2000&offset={off}'
    d = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=45) as r:
                d = json.load(r)
            break
        except Exception as e:
            print('retry', off, e, flush=True)
            time.sleep(4)
    if d is None:
        raise SystemExit('failed at offset ' + str(off))
    pages += 1
    ship_all += [x for x in d if x['subsector'] == 'international-shipping']
    print(f'page {pages}: {len(d)} rows, shipping total {len(ship_all)}', flush=True)
    if len(d) < 2000:
        break
    off += 2000
    time.sleep(1.2)

asia = [x for x in ship_all if x['country'] in ASIA]
out = [[x['id'], x['name'], x['country'], round(x['centroid']['latitude'], 4),
        round(x['centroid']['longitude'], 4), round(x['emissionsQuantity'] or 0),
        round(x['activity'] or 0), x.get('capacity') or 0, x['year']] for x in asia]
js = ('// Asia Green Corridors - international-shipping emissions census (Asian sources)\n'
      '// Source: Climate TRACE v7 API (CC BY 4.0), harvested 2026-09-05. Fields: id, name, ISO3, lat, lon,\n'
      '// emissions t CO2e(100yr), activity nmi, capacity (voyages+stays), year\n'
      '// Provenance note: API gas field = co2e_100yr (100-yr GWP); the API returns no per-record\n'
      '// release/version string, so the vintage of record is the access date (2026-09-05).\n'
      'window.SHIPPING = ' + json.dumps(out, separators=(',', ':')) + ';\n')
open('shipping_data.js', 'w', encoding='utf-8').write(js)
print('GLOBAL shipping sources:', len(ship_all), '| ASIAN:', len(asia),
      '| KB:', os.path.getsize('shipping_data.js') // 1024)
print('years:', sorted(set(x['year'] for x in ship_all)))
print('Asian total: %.1f Mt CO2e' % (sum(x[5] for x in out) / 1e6))
