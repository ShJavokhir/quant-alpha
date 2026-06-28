# Alpha101 on 2010–2014 US equities

Cross-sectional test of the WorldQuant **"101 Formulaic Alphas"** (Kakushadze, 2015)
on a daily panel of ~1,229 US stocks (2010–2014), built for the quant-alpha lab.

## TL;DR finding
The signals are **genuinely predictive but not tradeable at daily turnover**:
- Daily cross-sectional IC (corr of `alpha[t]` vs next-day return) is **positive for
  ~69 of 82 alphas and rises ~linearly 2010–2014** — and it survives a 1-day execution
  delay *and* a held-out half of the universe (out-of-asset).
- But net PnL **collapses under 10 bps of cost** (net-Sharpe>0 drops 68 → 4 of 82):
  these are 60–140%/day-turnover reversal signals; much of the edge is bid-ask bounce.

(82 of 101 alphas are implemented — the `cap`-based one and the ~18 needing sector data are skipped.)

## Setup
```bash
pip install -r requirements.txt
python fetch_reference.py        # downloads alpha101_ref.py (NOT vendored — see Attribution)
```

## Pipeline
```bash
python bulk_download.py          # 1. download S&P1500+ daily OHLCV -> data/<TICKER>_1d.csv
python build_panels.py           # 2. pivot to date x stock panels -> panels.pkl
python run_alphas.py             # 3. backtest all 82 alphas (parallel) -> results/alpha_*.csv
python configs_backtest.py       # 4. multi-config (delay/cost/out-of-asset) -> results/cfg_*.csv
python plot_alphas.py            # 5a. cumulative-IC + PnL grids
python plot_configs.py           # 5b. config-comparison grids + combined + attrition
```
Outputs land in `data/`, `panels.pkl`, and `results/` (all git-ignored).

## Files
| file | role |
|---|---|
| `bulk_download.py` | download daily OHLCV for S&P 1500 + Nasdaq-100 + Dow (yfinance, resumable, threaded) |
| `stats.py` | dataset summary stats |
| `build_panels.py` | pivot per-ticker CSVs into date x stock panels (+ `vwap≈(H+L+C)/3`, next-day return) |
| `alpha_engine.py` | **panel-correct** Alpha101 engine (see notes) |
| `run_alphas.py` | parallel backtest: daily IC (Spearman+Pearson) + dollar-neutral PnL |
| `configs_backtest.py` | same under 4 realism configs (base / delay-1 / +cost / out-of-asset) + combined top-20 blend |
| `plot_alphas.py`, `plot_configs.py` | the charts |
| `fetch_reference.py` | downloads the third-party formula file `alpha101_ref.py` |

## Methodology notes
- **Cross-sectional, as intended:** `rank`/`scale` act *across stocks* each day (axis=1).
  The popular single-stock ports rank over time — which is wrong for these formulas.
  Time-series ops (`delta`, `correlation`, `ts_*`, `decay_linear`) act per stock.
- The engine also vectorizes the slow `ts_rank`/`ts_argmax`/`product` with numpy sliding
  windows, int-coerces the paper's fractional windows, aliases `sum`→`ts_sum`, and rewrites
  the 7 methods that used single-stock-only idioms (`max`/`min` of two series, etc.).
- **IC** = daily cross-sectional correlation of `alpha[t]` with the next-day return;
  *cumulative IC* is its running sum (rising = persistent edge, flat = plateaued).
- **PnL** = dollar-neutral long/short, unit gross per day. `delay-1` trades on yesterday's
  signal; cost = 10 bps × turnover; out-of-asset = a deterministic held-out half of stocks.
- **Caveats:** gross numbers are in-sample to the alphas' 2015 publication; `vwap` is
  approximated (no intraday data); the universe is *current* index membership (survivorship bias).

## Attribution
- Formulas: Z. Kakushadze, *"101 Formulaic Alphas"* (2015), arXiv:1601.00991.
- `alpha101_ref.py` is fetched from
  <https://github.com/yli188/WorldQuant_alpha101_code> (file `101Alpha_code_1.py`).
  It is **not vendored** here because that repo carries no license; `fetch_reference.py`
  downloads it on demand.
