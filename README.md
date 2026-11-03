# Asia Green Corridors

**A zero-backend, browser-only observatory for Asia-Pacific ports and the Middle East–Asia green marine fuel corridor.**

Open `index.html` in any modern browser — no server, no account, no API key. All data are bundled in the five `*_data.js` files; live feeds are checked directly from your browser and the interface shows an explicit "unavailable" state rather than a fabricated value when a feed is blocked.

**Live site:** https://asia-green-corridors.netlify.app/

## What it does

- **Tab 1 — Port Observatory:** maps all 787 ports in IMF PortWatch's "Asia & Pacific" continent group, with daily vessel-call activity (satellite AIS, 2019–2026), Climate TRACE satellite-estimated shipping emissions (2025), and NOAA IBTrACS cyclone-track exposure since 2005.
- **Tab 2 — Corridor Watch & Scenarios:** a measured daily pulse for six Middle East–Asia corridor hubs (Fujairah, Singapore, Hong Kong, Shanghai, Ulsan, Salalah) and three chokepoints, plus a transparent three-lever decarbonisation scenario sandbox with an inverted IMO checkpoint solver.
- **Tab 3 — Method & Validation:** the anomaly-detection alarm is graded against 83 documented disruption events from the PortWatch log (2018–2026). Full results, including failures, are published in `validation/results.json` and reproduced by `validation_harness.py`.

## Files

| File | Contents |
|---|---|
| `index.html` | The complete dashboard (zero-backend; client-side only) |
| `ports_data.js` | Port universe: 787 ports with locations, annual calls, tanker shares |
| `shipping_data.js` | Climate TRACE port-area shipping emissions (2025 vintage) |
| `disruptions_data.js` | PortWatch documented disruption log (132 records) |
| `typhoons_data.js` | IBTrACS cyclone tracks relevant to the region since 2005 |
| `hubseries_data.js` | Daily vessel-call series for the six corridor hubs, to 23 October 2026 |
| `harvest_shipping.py` | Harvester for the Climate TRACE public API |
| `harvest_typhoons.py` | Harvester for NOAA IBTrACS |
| `harvest_validation.py` | Harvester for the PortWatch daily port series and disruption log |
| `validation_harness.py` | Reproduces every number in the validation table from the bundled data |
| `crosscheck_detectors.py` | Independent Python re-implementation of the browser's JS detectors (results identical) |
| `validation/results.json` | Full event-level validation output |
| `validation/port_series.json` | Daily traffic series for the 283 monitored ports (~20 MB; the raw evidence) |

## Reproduce the validation

```bash
python validation_harness.py
```

Requires Python 3.10+ with no third-party dependencies beyond the standard library. The harness reads `validation/port_series.json` and the disruption log and regenerates `validation/results.json`.

## Data sources and licences

| Source | Access | Licence |
|---|---|---|
| IMF PortWatch | keyless REST API | CC BY 4.0 |
| Climate TRACE | keyless REST API | CC BY 4.0 |
| NOAA IBTrACS | keyless | public domain |
| Open-Meteo Marine (live feed) | keyless | CC BY 4.0 |

## Citation

Companion preprint: *Asia Green Corridors: A Zero-Backend Browser Observatory for Port Activity, Emissions and Disruption Risk* (engrXiv, DOI to be inserted on publication). Empirical companion to Ng, K. W. P. (2026), *From Port to Platform*, Zenodo (doi:10.5281/zenodo.21639017).

## Disclaimer

Decision-support screening tool only. Not a trading system, a compliance calculation, or a substitute for verified IMO DCS / EU MRV data. Not investment, insurance or policy advice.
