"""Panel-correct Alpha101 engine.

Reuses the 82 alpha formulas from `alpha101_ref` (yli188's transcription) but:
  * makes the CROSS-SECTIONAL operators (rank, scale) act across stocks (axis=1);
  * vectorizes the slow time-series operators (ts_rank/argmax/argmin/product) with
    numpy sliding windows, and rewrites decay_linear as a shift-sum (uses RAM,
    saves CPU);
  * int-coerces every rolling window/period (the paper uses fractional ones);
  * aliases bare `sum`->`ts_sum` (the reference forgot to);
  * makes `.to_frame()`/`.CLOSE` no-ops on a panel (legacy single-column plumbing);
  * rewrites the 7 methods that used single-stock `pd.DataFrame({'p1','p2'})` /
    hardcoded-column idioms to use np.maximum/np.minimum/.where.

Each alpha runs on a fresh copy of the panels (the reference's alpha001 mutates
`close` in place).
"""
import warnings

import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

try:
    import alpha101_ref as ref
except ModuleNotFoundError:
    raise SystemExit(
        "alpha101_ref.py not found. It is not vendored (the source repo has no "
        "license). Run `python fetch_reference.py` once to download it."
    )

warnings.filterwarnings("ignore")
np.seterr(divide="ignore", invalid="ignore")
ANN = np.sqrt(252.0)


# ---------------- cross-sectional ops (across stocks, axis=1) ----------------
def rank(df):
    return df.rank(axis=1, pct=True)

def scale(df, k=1):
    denom = df.abs().sum(axis=1).replace(0, np.nan)
    return df.mul(k).div(denom, axis=0)


# ---------------- time-series ops (per stock, axis=0; int windows) -----------
def ts_sum(df, window=10):
    return df.rolling(int(window)).sum()

def sma(df, window=10):
    return df.rolling(int(window)).mean()

def stddev(df, window=10):
    return df.rolling(int(window)).std()

def correlation(x, y, window=10):
    return x.rolling(int(window)).corr(y)

def covariance(x, y, window=10):
    return x.rolling(int(window)).cov(y)

def ts_min(df, window=10):
    return df.rolling(int(window)).min()

def ts_max(df, window=10):
    return df.rolling(int(window)).max()

def delta(df, period=1):
    return df.diff(int(period))

def delay(df, period=1):
    return df.shift(int(period))


def _windows(df, window):
    a = df.to_numpy(dtype=float)
    return a, sliding_window_view(a, int(window), axis=0)   # (T-w+1, N, w)

def ts_rank(df, window=10):
    window = int(window)
    a, w = _windows(df, window)
    out = np.full(a.shape, np.nan)
    if a.shape[0] >= window:
        last = w[..., -1][..., None]
        out[window-1:] = (w < last).sum(-1) + ((w == last).sum(-1) + 1) / 2.0
    return pd.DataFrame(out, index=df.index, columns=df.columns)

def ts_argmax(df, window=10):
    window = int(window)
    a, w = _windows(df, window)
    out = np.full(a.shape, np.nan)
    if a.shape[0] >= window:
        out[window-1:] = np.nan_to_num(w, nan=-np.inf).argmax(-1) + 1
    return pd.DataFrame(out, index=df.index, columns=df.columns)

def ts_argmin(df, window=10):
    window = int(window)
    a, w = _windows(df, window)
    out = np.full(a.shape, np.nan)
    if a.shape[0] >= window:
        out[window-1:] = np.nan_to_num(w, nan=np.inf).argmin(-1) + 1
    return pd.DataFrame(out, index=df.index, columns=df.columns)

def product(df, window=10):
    window = int(window)
    a, w = _windows(df, window)
    out = np.full(a.shape, np.nan)
    if a.shape[0] >= window:
        out[window-1:] = np.nanprod(w, axis=-1)
    return pd.DataFrame(out, index=df.index, columns=df.columns)

def decay_linear(df, period=10):
    period = int(period)
    df = df.ffill().bfill().fillna(0.0)
    w = np.arange(1, period + 1, dtype=float)
    w /= w.sum()
    out = None
    for i in range(period):                    # newest day gets the largest weight
        term = df.shift(period - 1 - i) * w[i]
        out = term if out is None else out + term
    return out


# legacy single-column plumbing -> no-ops on a panel
pd.DataFrame.to_frame = lambda self, *a, **k: self
pd.DataFrame.CLOSE = property(lambda self: self)

# patch the reference module so its 82 formulas pick these up (incl. sum->ts_sum)
_OPS = dict(rank=rank, scale=scale, ts_sum=ts_sum, sum=ts_sum, sma=sma,
            stddev=stddev, correlation=correlation, covariance=covariance,
            ts_min=ts_min, ts_max=ts_max, delta=delta, delay=delay,
            ts_rank=ts_rank, ts_argmax=ts_argmax, ts_argmin=ts_argmin,
            product=product, decay_linear=decay_linear)
for _name, _fn in _OPS.items():
    setattr(ref, _name, _fn)

ALPHA_NAMES = sorted(n for n in dir(ref.Alphas)
                     if n.startswith("alpha") and n[5:].isdigit())

PANELS = None  # set in the worker before use


class PanelAlphas(ref.Alphas):
    """Feed our panels (copied), and rewrite the 7 single-stock-only methods."""
    def __init__(self, p):
        self.open = p["open"].copy()
        self.high = p["high"].copy()
        self.low = p["low"].copy()
        self.close = p["close"].copy()
        self.volume = p["volume"].copy()
        self.returns = p["returns"].copy()
        self.vwap = p["vwap"].copy()

    # Alpha#23  ((sma(high,20) < high) ? (-1 * delta(high,2)) : 0)
    def alpha023(self):
        cond = sma(self.high, 20) < self.high
        return (-1.0 * delta(self.high, 2)).where(cond, 0.0)

    # Alpha#71  max(p1, p2)
    def alpha071(self):
        adv180 = sma(self.volume, 180)
        p1 = ts_rank(decay_linear(correlation(ts_rank(self.close, 3), ts_rank(adv180, 12), 18), 4), 16)
        p2 = ts_rank(decay_linear(rank((self.low + self.open) - (self.vwap + self.vwap)).pow(2), 16), 4)
        return np.maximum(p1, p2)

    # Alpha#73  (max(p1, p2) * -1)
    def alpha073(self):
        p1 = rank(decay_linear(delta(self.vwap, 5), 3))
        base = (self.open * 0.147155) + (self.low * (1 - 0.147155))
        p2 = ts_rank(decay_linear((delta(base, 2) / base) * -1, 3), 17)
        return -1 * np.maximum(p1, p2)

    # Alpha#77  min(p1, p2)
    def alpha077(self):
        adv40 = sma(self.volume, 40)
        p1 = rank(decay_linear((((self.high + self.low) / 2) + self.high) - (self.vwap + self.high), 20))
        p2 = rank(decay_linear(correlation(((self.high + self.low) / 2), adv40, 3), 6))
        return np.minimum(p1, p2)

    # Alpha#88  min(p1, p2)
    def alpha088(self):
        adv60 = sma(self.volume, 60)
        p1 = rank(decay_linear(((rank(self.open) + rank(self.low)) - (rank(self.high) + rank(self.close))), 8))
        p2 = ts_rank(decay_linear(correlation(ts_rank(self.close, 8), ts_rank(adv60, 21), 8), 7), 3)
        return np.minimum(p1, p2)

    # Alpha#92  min(p1, p2)
    def alpha092(self):
        adv30 = sma(self.volume, 30)
        cond = ((((self.high + self.low) / 2) + self.close) < (self.low + self.open)).astype(float)
        p1 = ts_rank(decay_linear(cond, 15), 19)
        p2 = ts_rank(decay_linear(correlation(rank(self.low), rank(adv30), 8), 7), 7)
        return np.minimum(p1, p2)

    # Alpha#96  (max(p1, p2) * -1)
    def alpha096(self):
        adv60 = sma(self.volume, 60)
        p1 = ts_rank(decay_linear(correlation(rank(self.vwap), rank(self.volume), 4), 4), 8)
        p2 = ts_rank(decay_linear(ts_argmax(correlation(ts_rank(self.close, 7), ts_rank(adv60, 4), 4), 13), 14), 13)
        return -1 * np.maximum(p1, p2)


def _rowwise_corr(a, b):
    a = a.sub(a.mean(axis=1), axis=0)
    b = b.sub(b.mean(axis=1), axis=0)
    den = np.sqrt((a ** 2).sum(axis=1) * (b ** 2).sum(axis=1)).replace(0, np.nan)
    return (a * b).sum(axis=1) / den


def compute_and_backtest(name, panels=None):
    """Compute one alpha; return daily IC series (alpha[t] vs next-day return),
    daily long/short PnL, and summary metrics."""
    p = panels if panels is not None else PANELS
    sig = getattr(PanelAlphas(p), name)()
    if not isinstance(sig, pd.DataFrame):
        sig = pd.DataFrame(sig)
    sig = sig.reindex(index=p["close"].index, columns=p["close"].columns)
    sig = sig.astype(float).replace([np.inf, -np.inf], np.nan)
    fwd = p["fwd"]

    # ---- daily cross-sectional Information Coefficient: corr(alpha[t], ret[t+1]) ----
    ic_rank = _rowwise_corr(sig.rank(axis=1), fwd.rank(axis=1))   # Spearman (rank IC)
    ic_pear = _rowwise_corr(sig, fwd)                             # Pearson

    # ---- dollar-neutral long/short portfolio PnL (reference) ----
    w = sig.sub(sig.mean(axis=1), axis=0)
    w = w.div(w.abs().sum(axis=1).replace(0, np.nan), axis=0)
    pnl = (w * fwd).sum(axis=1, min_count=1).fillna(0.0)

    icr = ic_rank.dropna()
    sd = pnl.std()
    metrics = {
        "ic": float(icr.mean()) if len(icr) else 0.0,
        "ic_ir": float(ANN * icr.mean() / icr.std()) if len(icr) and icr.std() > 0 else 0.0,
        "ic_hit": float((icr > 0).mean()) if len(icr) else 0.0,   # % days corr>0
        "ic_pearson": float(ic_pear.dropna().mean()) if ic_pear.notna().any() else 0.0,
        "sharpe": float(ANN * pnl.mean() / sd) if sd and sd > 0 else 0.0,
        "ann_ret": float(pnl.mean() * 252),
        "turnover": float(w.diff().abs().sum(axis=1).mean()),
        "active_days": int((pnl != 0).sum()),
    }
    series = {"pnl": pnl, "ic_rank": ic_rank, "ic_pear": ic_pear}
    return name, series, metrics
