"""Backtest a signal/formula -> IC, IC-IR, appraisal ratio, turnover, cost-aware PnL.

Conventions (match the validated alpha101 harness):
  * signal[t] is ranked cross-sectionally; we trade a dollar-neutral, unit-gross
    long/short book and capture fwd[t] = next-day return.
  * IC = daily cross-sectional rank corr( signal[t], fwd[t] ).  IC-IR = ANN * mean/std.
  * appraisal ratio = beta-adjusted (vs equal-weight market) info ratio of the PnL.
  * net PnL subtracts cost_bps * turnover each day (10 bps default = realism gate).
"""
import numpy as np
import pandas as pd

ANN = np.sqrt(252.0)


def _rowwise_corr(a: pd.DataFrame, b: pd.DataFrame) -> pd.Series:
    a = a.sub(a.mean(axis=1), axis=0)
    b = b.sub(b.mean(axis=1), axis=0)
    den = np.sqrt((a ** 2).sum(axis=1) * (b ** 2).sum(axis=1)).replace(0, np.nan)
    return (a * b).sum(axis=1) / den


def _slice(df, start, end):
    if start is not None:
        df = df.loc[df.index >= pd.Timestamp(start)]
    if end is not None:
        df = df.loc[df.index <= pd.Timestamp(end)]
    return df


def weights_from_signal(sig: pd.DataFrame) -> pd.DataFrame:
    """Dollar-neutral, unit-gross weights from a raw signal."""
    w = sig.sub(sig.mean(axis=1), axis=0)
    return w.div(w.abs().sum(axis=1).replace(0, np.nan), axis=0)


def evaluate_signal(sig: pd.DataFrame, panel: dict, start=None, end=None,
                    cost_bps: float = 10.0, with_series: bool = False) -> dict:
    fwd = panel["fwd"]
    sig = _slice(sig, start, end)
    fwd = fwd.reindex(index=sig.index, columns=sig.columns)

    ic_rank = _rowwise_corr(sig.rank(axis=1), fwd.rank(axis=1))
    ic_pear = _rowwise_corr(sig, fwd)

    w = weights_from_signal(sig)
    pnl = (w * fwd).sum(axis=1, min_count=1).fillna(0.0)
    turn = w.diff().abs().sum(axis=1)
    net = pnl - (cost_bps / 1e4) * turn.fillna(0.0)

    # market (equal-weight) and beta-adjusted appraisal ratio of the gross PnL
    mkt = fwd.mean(axis=1)
    appraisal, beta = _appraisal(pnl, mkt)
    appraisal_net, _ = _appraisal(net, mkt)

    icr = ic_rank.dropna()
    sd, sdn = pnl.std(), net.std()
    m = {
        "ic": _f(icr.mean()),
        "ic_ir": _f(ANN * icr.mean() / icr.std()) if len(icr) and icr.std() > 0 else 0.0,
        "ic_hit": _f((icr > 0).mean()) if len(icr) else 0.0,
        "ic_pearson": _f(ic_pear.dropna().mean()) if ic_pear.notna().any() else 0.0,
        "sharpe": _f(ANN * pnl.mean() / sd) if sd and sd > 0 else 0.0,
        "sharpe_net": _f(ANN * net.mean() / sdn) if sdn and sdn > 0 else 0.0,
        "appraisal": appraisal,
        "appraisal_net": appraisal_net,
        "beta": beta,
        "ann_ret": _f(pnl.mean() * 252),
        "ann_ret_net": _f(net.mean() * 252),
        "turnover": _f(turn.mean()),
        "n_days": int(len(icr)),
    }
    if with_series:
        m["_series"] = {"pnl": pnl, "net": net, "ic_rank": ic_rank, "weights": w}
    return m


def _appraisal(pnl: pd.Series, mkt: pd.Series):
    df = pd.concat([pnl, mkt], axis=1).dropna()
    if len(df) < 30 or df.iloc[:, 1].std() == 0:
        sd = pnl.std()
        return (_f(ANN * pnl.mean() / sd) if sd and sd > 0 else 0.0), 0.0
    y, x = df.iloc[:, 0].to_numpy(), df.iloc[:, 1].to_numpy()
    beta = np.cov(y, x)[0, 1] / np.var(x)
    resid = y - beta * x
    a = resid.mean()
    rs = resid.std()
    return (_f(ANN * a / rs) if rs > 0 else 0.0), _f(beta)


def _f(x):
    try:
        x = float(x)
        return x if np.isfinite(x) else 0.0
    except (TypeError, ValueError):
        return 0.0
