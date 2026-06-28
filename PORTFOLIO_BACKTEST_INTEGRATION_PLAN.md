# Portfolio Backtest Integration Plan

## Goal

Incorporate the useful parts of the attached legacy alpha/backtesting zip into this platform without porting the old codebase wholesale.

The target is a modern, test-driven cross-sectional factor backtesting pipeline that coexists with the current single-instrument strategy pipeline:

- Current pipeline: `strategies.py` -> `walkforward.py` -> `research.py` -> `api.py` -> frontend.
- New pipeline: data panel -> factor registry -> portfolio construction -> portfolio backtest -> factor walk-forward -> API -> frontend.

The legacy zip should be treated as a reference implementation for concepts:

- Cross-sectional alpha matrices, date x ticker.
- Daily and intraday factor formulas.
- Neutralization, alpha decay, ranking, top/bottom portfolio construction.
- Long-only, short-only, long/short, and quantile evaluation.
- IC, RankIC, turnover, and PnL reporting.

It should not be imported directly. The old stack uses Python 2 syntax, Windows paths, missing local modules, Oracle/HDF5 assumptions, and China A-share-specific data fields that are not present in this repo.

## Non-Goals

- Do not rewrite the existing demo pipeline.
- Do not port every alpha formula from the zip.
- Do not require intraday data for the first integration.
- Do not claim Yahoo Finance is sufficient for institutional-grade cross-sectional testing.
- Do not add a database before the local-file replay path is stable.

## Guiding Principles

- Test first: each slice starts with a failing test that defines behavior.
- Keep the old single-name backtester intact.
- Introduce a separate portfolio/factor path with shared metric helpers where useful.
- All signals must be shifted before returns are applied.
- Data access must be explicit and auditable.
- The platform should degrade gracefully when optional fields are missing.
- Yahoo Finance is acceptable for prototype daily OHLCV factors only.

## Proposed File Layout

```text
requirements.txt
tests/
  conftest.py
  test_data_panel.py
  test_factors.py
  test_portfolio_backtest.py
  test_factor_walkforward.py
  test_api_portfolio.py

data_panel.py
factors/
  __init__.py
  registry.py
  technical.py
  cross_sectional.py
portfolio.py
portfolio_backtest.py
factor_walkforward.py

api.py                         # extend only after core tests pass
frontend/lib/api.ts            # extend types after API contract is stable
frontend/components/...         # add portfolio/factor panels later
```

If the repo later grows, these can move under `src/`, but for now the root-level Python style matches the existing codebase.

## Milestone 0: Dependency And Test Harness

### Scope

Create a minimal reproducible Python environment and test harness.

### Implementation

- Add `requirements.txt`.
- Include runtime dependencies already implied by the repo:
  - `pandas`
  - `numpy`
  - `matplotlib`
  - `fastapi`
  - `uvicorn[standard]`
  - `pydantic`
  - `yfinance`
- Include test dependencies:
  - `pytest`
  - `httpx`
- Optional, later:
  - `scipy`
  - `scikit-learn`
  - `TA-Lib` or a pure-Python substitute such as `pandas-ta`

### Tests To Write First

No business tests yet. Add a simple smoke test:

```python
def test_test_harness_imports():
    import pandas
    import numpy
```

### How To Test

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest
```

### Acceptance Criteria

- `pytest` runs locally.
- No existing demo files are modified.
- Python dependencies are documented in one place.

## Milestone 1: Data Panel Abstraction

### Scope

Create the platform data shape that both Yahoo-backed prototype data and richer licensed data can feed.

### Data Contract

The canonical daily panel should support:

```python
PanelData(
    open: DataFrame[date x ticker],
    high: DataFrame[date x ticker],
    low: DataFrame[date x ticker],
    close: DataFrame[date x ticker],
    adj_close: DataFrame[date x ticker] | None,
    volume: DataFrame[date x ticker],
    vwap: DataFrame[date x ticker] | None,
    returns: DataFrame[date x ticker],
    tradable: DataFrame[date x ticker],
    universe: DataFrame[date x ticker],
    metadata: dict,
)
```

For current local CSVs, build `PanelData` from `data/*_1d.csv`.

### Implementation

Add `data_panel.py`:

- `PanelData` dataclass.
- `load_local_ohlcv_panel(data_dir, tickers=None, start=None, end=None)`.
- `align_frames(frames)`.
- `compute_returns(close)`.
- `default_tradable(open, close, volume)`.
- `default_universe(close)`.
- `validate_panel(panel)`.

### Tests To Write First

`tests/test_data_panel.py`:

- `test_load_local_panel_aligns_dates_and_columns`
  - Given two synthetic CSVs with overlapping but not identical dates.
  - Expect aligned DataFrames and sorted columns.
- `test_returns_are_close_to_close_and_do_not_peek`
  - Given close `[100, 110, 99]`.
  - Expect returns `[0, 0.10, -0.10]` or first row filled as configured.
- `test_tradable_false_when_volume_missing_or_zero`
  - Given zero volume on one day.
  - Expect `tradable` false for that asset/date.
- `test_validate_panel_rejects_misaligned_frames`
  - Construct mismatched indexes.
  - Expect `ValueError`.

### How To Test

```bash
pytest tests/test_data_panel.py
```

### Acceptance Criteria

- All local CSV data can be represented as a panel.
- Missing optional fields do not break loading.
- Required fields are aligned and validated.

## Milestone 2: Factor Registry

### Scope

Port a small, representative set of daily factors from the legacy zip into modern, tested functions.

Start with factors that only require daily OHLCV:

- `sma_gap`: short moving average minus long moving average.
- `rsi_reversion_score`: lower RSI means higher reversion score.
- `volume_price_corr`: rolling correlation of ranked volume change and intraday return.
- `alpha_5_like`: rank(open minus rolling vwap proxy) times rank(close minus vwap proxy), adapted to daily data.
- `momentum_20`: trailing 20-day return.

Do not port intraday FFT/convolution factors until intraday data exists.

### Implementation

Add `factors/registry.py`:

- `FactorSpec` dataclass:
  - `name`
  - `kind`
  - `required_fields`
  - `params`
  - `fn`
  - `description`
- `register_factor`.
- `get_factor`.
- `list_factors`.
- `evaluate_factor(panel, name, params)`.

Add `factors/technical.py`:

- Rolling helpers.
- Cross-sectional rank helper.
- Winsorize/z-score helper.
- Initial factor functions.

Add `factors/cross_sectional.py`:

- Neutralization helpers added in Milestone 5.

### Tests To Write First

`tests/test_factors.py`:

- `test_factor_registry_lists_initial_factors`
  - Expect known factor names.
- `test_evaluate_factor_returns_date_by_ticker_frame`
  - Given synthetic panel.
  - Expect same index and columns.
- `test_factor_does_not_use_future_data`
  - Change future close values.
  - Expect factor values before that date unchanged.
- `test_factor_required_fields_are_enforced`
  - Remove `volume`.
  - Expect clear error for volume-based factor.
- `test_cross_sectional_rank_is_per_date`
  - Given a small matrix.
  - Expect ranks computed across tickers for each date.

### How To Test

```bash
pytest tests/test_factors.py
```

### Acceptance Criteria

- At least three daily OHLCV factors work.
- No factor depends on future rows.
- Every factor has metadata usable by the API/UI.

## Milestone 3: Portfolio Construction

### Scope

Turn factor scores into daily target weights.

This is the modern equivalent of the legacy evaluator's `get_long_position`, `get_short_position`, and quantile selection logic.

### Implementation

Add `portfolio.py`:

- `PortfolioConfig` dataclass:
  - `mode`: `long_only`, `short_only`, `long_short`, `quantile`
  - `top_quantile`
  - `bottom_quantile`
  - `top_n`
  - `weighting`: `equal`, `score`
  - `gross_exposure`
  - `net_exposure`
  - `rebalance_every`
- `rank_scores(scores, ascending=False)`.
- `select_universe(scores, universe, tradable)`.
- `weights_from_scores(scores, config, universe, tradable)`.
- `apply_rebalance_schedule(weights, every_n_days)`.

### Behavior Rules

- Long-only top quantile sums to `+1`.
- Short-only bottom quantile sums to `-1`.
- Long/short top and bottom each use half gross exposure by default.
- Assets outside `universe` or not `tradable` receive zero weight.
- If no assets are selectable on a date, weights are zero.
- Position weights are target weights decided at the close of date `t`.

### Tests To Write First

`tests/test_portfolio_backtest.py` or separate `tests/test_portfolio.py`:

- `test_long_only_top_quantile_weights_sum_to_one`
- `test_long_short_weights_are_dollar_neutral`
- `test_untradable_assets_get_zero_weight`
- `test_empty_selection_returns_zero_weights`
- `test_rebalance_schedule_holds_prior_weights_between_rebalances`
- `test_score_weighting_preserves_direction_and_normalizes`

### How To Test

```bash
pytest tests/test_portfolio_backtest.py
```

### Acceptance Criteria

- Target weights are deterministic.
- Gross and net exposure constraints are explicit.
- Tradability and universe masks are honored.

## Milestone 4: Portfolio Backtester

### Scope

Build a vectorized portfolio backtester for multi-asset target weights.

This should mirror the current `backtest.py` execution discipline:

- Target weights at date `t` are decided after date `t` data.
- They earn returns from date `t+1`.
- Turnover cost is charged when positions change.

### Implementation

Add `portfolio_backtest.py`:

- `run_portfolio_backtest(panel, target_weights, commission_bps=2, slippage_bps=3)`.
- `compute_portfolio_metrics(result, benchmark_returns=None)`.
- `information_coefficient(scores, future_returns, method="spearman")`.
- `quantile_returns(scores, future_returns, n_quantiles=5)`.

Result shape:

```python
{
    "weights": DataFrame,
    "held_weights": DataFrame,
    "asset_returns": DataFrame,
    "gross_returns": Series,
    "turnover": Series,
    "costs": Series,
    "net_returns": Series,
    "equity": Series,
    "gross_exposure": Series,
    "net_exposure": Series,
}
```

### Tests To Write First

`tests/test_portfolio_backtest.py`:

- `test_portfolio_backtest_shifts_weights_before_returns`
  - Give weights that go long before a known return.
  - Verify first row earns zero and second row earns prior target.
- `test_turnover_costs_charged_on_weight_changes`
  - Weight from 0 to 1 with 5 bps cost.
  - Expect cost on the trade date.
- `test_long_short_returns_sum_asset_contributions`
  - Two assets, one long and one short.
  - Verify daily return equals weighted asset returns.
- `test_metrics_include_sharpe_drawdown_turnover_exposure`
- `test_information_coefficient_uses_future_returns`
  - Scores on `t` correlate with returns on `t+1`, not `t`.
- `test_quantile_returns_are_monotonic_for_synthetic_perfect_factor`

### How To Test

```bash
pytest tests/test_portfolio_backtest.py
```

### Acceptance Criteria

- No-lookahead behavior is proven with tests.
- Costs and turnover are tested.
- IC and quantile return helpers work on synthetic data.

## Milestone 5: Neutralization And Data Quality Filters

### Scope

Add a minimal modern equivalent of the legacy evaluator's `advanced_res`, alpha decay, and filters.

This must be optional because Yahoo data will not provide full style/industry panels by default.

### Implementation

In `factors/cross_sectional.py`:

- `winsorize_by_mad(series, level=5)`.
- `zscore_cross_section(series)`.
- `neutralize_one_day(y, exposures)`.
- `neutralize_panel(scores, exposures_by_name)`.
- `ema_decay_scores(scores, span)`.

In `data_panel.py`:

- Optional `industry` and `exposures` hooks can be added later.

### Tests To Write First

`tests/test_factors.py`:

- `test_winsorize_caps_outliers`
- `test_zscore_has_zero_mean_unit_std_per_date`
- `test_neutralize_removes_linear_size_exposure`
- `test_neutralize_preserves_index_and_columns`
- `test_ema_decay_uses_only_past_scores`

### How To Test

```bash
pytest tests/test_factors.py
```

### Acceptance Criteria

- Neutralization is optional.
- Missing exposures produce a clear error only when neutralization is requested.
- Decay is causal.

## Milestone 6: Factor Walk-Forward Evaluation

### Scope

Bring the new portfolio pipeline into the platform's research loop pattern.

### Implementation

Add `factor_walkforward.py`:

- `FactorProposal` dataclass:
  - `factor_name`
  - `factor_params`
  - `portfolio_config`
  - `neutralization`
  - `windows`
- `evaluate_factor_proposal(panel, proposal)`.
- `walk_forward_factor(panel, proposal, is_years, oos_years, step_years)`.
- `optimize_factor_params(panel, factor_name, param_grid, portfolio_grid, objective)`.
- `factor_verdict(folds)`.

Initial objective candidates:

- OOS appraisal ratio vs equal-weight benchmark.
- OOS information ratio vs equal-weight benchmark.
- IC mean / IC std.
- Return spread of top quantile minus bottom quantile.

Recommendation:

- Use IC and long/short portfolio metrics together.
- A factor can pass only if IC is positive and the long/short OOS portfolio has acceptable risk-adjusted returns after costs.

### Tests To Write First

`tests/test_factor_walkforward.py`:

- `test_walk_forward_factor_creates_non_overlapping_oos_folds`
- `test_optimizer_uses_only_in_sample_window`
- `test_factor_verdict_marks_negative_oos_as_overfit`
- `test_factor_verdict_marks_high_is_oos_gap_as_fragile`
- `test_factor_verdict_marks_stable_positive_oos_as_robust`
- `test_deleted_early_verdict_changes_routing_for_factor_family`

### How To Test

```bash
pytest tests/test_factor_walkforward.py
```

### Acceptance Criteria

- Factor proposals can be scored across rolling windows.
- The scoring result can be represented in the existing journal style.
- Tests prove no training data leaks into OOS scoring.

## Milestone 7: Research Loop Integration

### Scope

Let the current `research.py` loop understand both strategy templates and factor proposals.

### Implementation Options

Preferred:

- Add a separate `factor_research.py` first.
- Keep `research.py` unchanged until the new path is stable.

Later:

- Generalize the proposal schema into:
  - `kind`: `single_asset_strategy` or `cross_sectional_factor`
  - `template` or `factor_name`
  - `grid`
  - `portfolio_config`

Add journal fields:

```json
{
  "pipeline": "factor",
  "factor_name": "momentum_20",
  "factor_params": {"lookback": 20},
  "portfolio": {"mode": "long_short", "top_quantile": 0.2},
  "ic_mean": 0.03,
  "ic_ir": 0.45,
  "turnover": 0.31,
  "gross_exposure": 1.0,
  "net_exposure": 0.0
}
```

### Tests To Write First

`tests/test_factor_walkforward.py` or `tests/test_factor_research.py`:

- `test_factor_research_writes_journal_records`
- `test_factor_research_records_ic_turnover_and_portfolio_config`
- `test_factor_research_stops_after_robust_when_configured`
- `test_factor_research_routes_away_from_overfit_family`

### How To Test

```bash
pytest tests/test_factor_walkforward.py
```

### Acceptance Criteria

- A factor research run writes replayable JSONL.
- The existing demo run is not broken.
- The frontend can continue reading old journal records.

## Milestone 8: API Endpoints

### Scope

Expose portfolio/factor backtests through FastAPI.

### Implementation

Extend `api.py` after the core is tested:

- `GET /api/factors`
  - list factor metadata.
- `POST /api/portfolio-backtests`
  - run one factor portfolio backtest from a request body.
- `GET /api/runs/{run_id}/factor-journal`
  - optional if factor research writes a separate artifact.
- `GET /api/portfolio-backtests/{id}/equity`
  - can be file-backed initially.
- `GET /api/portfolio-backtests/{id}/ic`
- `GET /api/portfolio-backtests/{id}/quantiles`
- `GET /api/portfolio-backtests/{id}/positions`

Use Pydantic models:

- `FactorBacktestRequest`.
- `PortfolioConfigModel`.
- `FactorBacktestResponse`.

### Tests To Write First

`tests/test_api_portfolio.py`:

- `test_get_factors_returns_registry`
- `test_post_portfolio_backtest_returns_equity_and_metrics`
- `test_post_portfolio_backtest_rejects_unknown_factor`
- `test_post_portfolio_backtest_rejects_invalid_quantile`
- `test_api_response_is_json_serializable`

### How To Test

```bash
pytest tests/test_api_portfolio.py
```

### Acceptance Criteria

- API endpoints are covered without needing the Next frontend.
- Errors are clear and typed.
- Existing `/api/runs/latest/journal` still works.

## Milestone 9: Frontend Integration

### Scope

Add a useful portfolio backtesting surface without turning the app into a landing page.

### UI Additions

- Factor selector.
- Portfolio construction controls:
  - mode
  - top/bottom quantile
  - weighting
  - rebalance frequency
  - costs
- Results:
  - equity curve
  - benchmark comparison
  - IC time series
  - quantile return chart
  - turnover/exposure stats
  - current/last holdings table

### Implementation

Extend:

- `frontend/lib/api.ts`
- add `frontend/components/FactorBacktestPanel.tsx`
- add `frontend/components/FactorMetricCards.tsx`
- add `frontend/components/QuantileReturns.tsx`

Keep the first version dense and operational.

### Tests To Write First

If frontend test tooling is not present, start with build/lint checks:

```bash
cd frontend
npm install
npm run lint
npm run build
```

If adding component tests later:

- Factor selector renders factors from mocked API.
- Submit button sends valid request body.
- Error state renders API validation failures.
- Empty result state does not crash charts.

### Acceptance Criteria

- Frontend builds.
- Existing dashboard still renders.
- User can run a factor backtest from the UI against local data.

## Milestone 10: Yahoo Finance Provider

### Scope

Add a Yahoo-backed data provider only for prototype daily US-equity OHLCV factors.

### Implementation

Add to `data_panel.py` or `data_providers/yahoo.py`:

- `download_yahoo_panel(tickers, start, end, interval="1d")`.
- Normalize columns into `PanelData`.
- Store downloaded CSV cache under `data/cache/yahoo/` or a configured path.
- Record provider metadata:
  - provider
  - download timestamp
  - interval
  - adjusted flag
  - missing tickers

### Important Limitations To Surface In UI/API

Yahoo/yfinance is enough for:

- Daily OHLCV prototype factors.
- US large-cap demos.
- Basic adjusted-price backtests.

Yahoo/yfinance is not enough for:

- Survivorship-free universe studies.
- Delisted stocks.
- Point-in-time index constituents.
- Full historical market cap/style/industry exposures.
- Suspension and limit-up/limit-down masks.
- Reliable institutional intraday history.
- Commercial data redistribution.

### Tests To Write First

Do not make unit tests depend on live Yahoo network calls.

`tests/test_data_panel.py`:

- `test_yahoo_normalizer_handles_multiindex_columns`
- `test_yahoo_normalizer_records_missing_tickers`
- `test_yahoo_provider_cache_roundtrip`

Integration test, optional and skipped by default:

```python
@pytest.mark.integration
def test_yahoo_download_smoke():
    ...
```

### How To Test

Offline:

```bash
pytest tests/test_data_panel.py
```

Optional live:

```bash
pytest -m integration
```

### Acceptance Criteria

- Live network is not required for normal CI/local tests.
- Provider limitations are visible in docs and response metadata.
- Cached data can replay a prior Yahoo-backed test.

## Milestone 11: Demo Artifact Generation

### Scope

Create a committed replay artifact for factor backtests, similar to `runs/demo_committed`.

### Implementation

Add:

- `build_factor_demo.py`, or extend `build_demo.py` behind a flag.
- `runs/factor_demo_committed/`
  - `factor_journal.jsonl`
  - `portfolio_backtest.json`
  - `ic.json`
  - `quantiles.json`
  - `summary.json`

Use local CSVs first. Do not depend on live Yahoo for the committed replay.

### Tests To Write First

`tests/test_factor_walkforward.py`:

- `test_factor_demo_artifact_schema`
- `test_factor_demo_replay_loads_without_network`

### How To Test

```bash
python build_factor_demo.py --quick
pytest tests/test_factor_walkforward.py
```

### Acceptance Criteria

- Demo artifacts are deterministic.
- API can serve them without recomputing everything.
- No live network is needed for demo playback.

## Data Provider Decision Matrix

| Need | Yahoo/yfinance | Licensed market data |
|---|---:|---:|
| Daily US OHLCV prototype | Yes | Yes |
| Adjusted close / splits / dividends | Partial/usable | Yes |
| Intraday long history | Limited | Yes |
| Survivorship-free universes | No | Yes |
| Delisted stocks | No | Yes |
| Historical index constituents | No | Yes |
| Industry/style exposures | No | Yes |
| Market cap history | Partial/manual | Yes |
| VWAP | No or derived approximation | Yes |
| Trading halts/suspensions | No | Yes |
| Limit-up/limit-down masks | No | Yes, for markets that need it |
| Commercial redistribution | Not appropriate | Contract-dependent |

## Testing Strategy Summary

### Unit Tests

- Data alignment.
- Causal rolling factor calculation.
- Ranking and weighting.
- Position shifting.
- Turnover/cost accounting.
- IC and quantile return math.
- Neutralization residuals.

### Integration Tests

- Local CSV panel -> factor -> portfolio weights -> backtest metrics.
- Factor proposal -> walk-forward folds -> verdict.
- API request -> JSON response.
- Demo artifact -> API replay.

### Regression Tests

- Existing single-name strategy APIs still work.
- Existing `runs/demo_committed` loads.
- Existing frontend TypeScript types remain compatible.

### Optional Live Tests

- Yahoo download smoke test.
- Marked and skipped by default.

## Suggested Implementation Order

1. Milestone 0: dependencies and pytest.
2. Milestone 1: data panel.
3. Milestone 2: factor registry with simple factors.
4. Milestone 3: portfolio construction.
5. Milestone 4: portfolio backtester.
6. Milestone 6: factor walk-forward.
7. Milestone 8: API endpoints.
8. Milestone 9: frontend.
9. Milestone 10: Yahoo provider.
10. Milestone 11: committed factor demo.
11. Milestone 5 neutralization can be done after Milestone 4 or after Milestone 6, depending on urgency.

## First Pull Request Scope

Keep the first implementation PR small enough to review:

- `requirements.txt`
- `data_panel.py`
- `factors/registry.py`
- `factors/technical.py`
- `portfolio.py`
- `portfolio_backtest.py`
- tests for those modules

Leave API/frontend/factor walk-forward for the next PR.

## First PR Acceptance Criteria

- `pytest` passes.
- A synthetic factor can produce a long/short portfolio.
- Portfolio returns are shifted correctly.
- Costs and turnover are tested.
- Local CSVs can be loaded into `PanelData`.
- Existing root scripts remain untouched unless required for imports.

## Risk Register

| Risk | Mitigation |
|---|---|
| Lookahead bias | Dedicated tests for shifted positions and future-value mutation. |
| Yahoo data limitations | Treat Yahoo as prototype provider and expose metadata warnings. |
| Legacy code complexity | Port formulas and concepts selectively; do not import old modules. |
| Frontend scope creep | Build core API and artifacts first. |
| Dependency friction around TA-Lib | Start with pandas/numpy implementations. Add TA-Lib-compatible wrappers later. |
| Survivorship bias | Keep warning in provider metadata; add licensed provider abstraction later. |
| Metric overclaiming | Report IC, turnover, costs, benchmark-relative returns, and drawdowns together. |

## Open Questions

- Should the first cross-sectional universe be the current 15 ticker basket, or a larger Yahoo-derived list?
- Should the first factor demo be long/short dollar-neutral, long-only, or both?
- Should factor verdicts gate on portfolio appraisal ratio, IC IR, or a combined rule?
- Do we want the LLM to propose factors immediately, or first ship manual factor backtests?
- Which licensed data provider is the intended production target after Yahoo prototype support?

