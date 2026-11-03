"""Harvest IBTrACS W. Pacific typhoon tracks -> compact typhoons_data.js bundle.

Keeps WPAC storms from 2005 onward, 6-hourly synoptic points only, as integer-scaled
arrays. Source: NOAA IBTrACS v04r01 (public domain), harvested 2026-09-05.
"""
import csv
import json
import os
import urllib.request

URL = ('https://www.ncei.noaa.gov/data/international-best-track-archive-for-climate-'
       'stewardship-ibtracs/v04r01/access/csv/ibtracs.WP.list.v04r01.csv')
RAW = 'ibtracs_wp.csv'

if not os.path.exists(RAW):
    print('downloading ~109 MB...', flush=True)
    urllib.request.urlretrieve(URL, RAW)
print('size MB:', os.path.getsize(RAW) // 1048576, flush=True)

storms = {}
with open(RAW, newline='', encoding='utf-8', errors='replace') as f:
    rdr = csv.reader(f)
    header = next(rdr)
    units = next(rdr)  # second row = units
    ix = {k: header.index(k) for k in
          ('SID', 'SEASON', 'NAME', 'ISO_TIME', 'LAT', 'LON', 'USA_WIND', 'USA_SSHS')}
    for row in rdr:
        try:
            season = int(row[ix['SEASON']])
        except ValueError:
            continue
        if season < 2005:
            continue
        hour = row[ix['ISO_TIME']][11:13]
        if hour not in ('00', '06', '12', '18'):
            continue
        try:
            lat = float(row[ix['LAT']]); lon = float(row[ix['LON']])
        except ValueError:
            continue
        wind = row[ix['USA_WIND']]
        wind = int(float(wind)) if wind not in ('', ' ') else -1
        sid = row[ix['SID']]
        s = storms.setdefault(sid, {'name': row[ix['NAME']].strip(), 'season': season,
                                    'pts': [], 'maxw': 0})
        s['pts'].append([round(lat * 10), round(lon * 10), wind])
        if wind > s['maxw']:
            s['maxw'] = wind

out = []
for sid, s in storms.items():
    if s['maxw'] >= 34 and len(s['pts']) >= 4:   # at least tropical-storm strength, real track
        name = s['name'] if s['name'] and s['name'] != 'NOT_NAMED' else sid
        out.append([sid, name, s['season'], s['maxw'], s['pts']])
out.sort(key=lambda s: (s[2], s[0]))

js = ('// Asia Green Corridors - W. Pacific tropical cyclone tracks (IBTrACS v04r01, public domain)\n'
      '// Harvested 2026-09-05 from NOAA NCEI. Storms 2005+, >=34 kt, 6-hourly points.\n'
      '// Fields: SID, name, season, max USA wind (kt), points [[lat*10, lon*10, wind kt], ...]\n'
      'window.TYPHOONS = ' + json.dumps(out, separators=(',', ':')) + ';\n')
open('typhoons_data.js', 'w', encoding='utf-8').write(js)
print('storms kept:', len(out), '| KB:', os.path.getsize('typhoons_data.js') // 1024)
print('seasons:', out[0][2], '-', out[-1][2])
print('strongest:', max(out, key=lambda s: s[3])[:4])
