"""Alpha operator library — panel-correct, mirrors the validated alpha101 engine.

Cross-sectional ops (rank, scale) act ACROSS stocks each day (axis=1).
Time-series ops (delta, correlation, ts_*, decay_linear) act per stock (axis=0).
Every rolling window is int-coerced (the WorldQuant paper uses fractional ones).

These are the ONLY callables exposed to the DSL sandbox, so they must be total
(never raise) and always return a DataFrame aligned to the input panel.
"""
import warnings
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

warnings.filterwarnings("ignore")
np.seterr(divide="ignore", invalid="ignore")


def _df(x):
    return x if isinstance(x, pd.DataFrame) else pd.DataFrame(x)


# ---------------- cross-sectional (across stocks, axis=1) ----------------
def rank(x):
    return _df(x).rank(axis=1, pct=True)


def scale(x, k=1):
    x = _df(x)
    denom = x.abs().sum(axis=1).replace(0, np.nan)
    return x.mul(k).div(denom, axis=0)


def indneutralize(x, *_):
    """No sector/industry data available -> demean cross-sectionally (best effort)."""
    x = _df(x)
    return x.sub(x.mean(axis=1), axis=0)


# ---------------- element-wise ----------------
def log(x):
    return np.log(_df(x).clip(lower=1e-12))


def sign(x):
    return np.sign(_df(x))


def abs_(x):
    return _df(x).abs()


def signedpower(x, a):
    x = _df(x)
    return np.sign(x) * (x.abs() ** a)


def maximum(x, y):
    return _df(x).where(_df(x) > _df(y), _df(y)) if isinstance(y, (pd.DataFrame,)) else _df(x).clip(lower=y)


def minimum(x, y):
    return _df(x).where(_df(x) < _df(y), _df(y)) if isinstance(y, (pd.DataFrame,)) else _df(x).clip(upper=y)


def iif(cond, a, b):
    """Ternary: where cond is true take a else b. cond is a boolean DataFrame."""
    cond = _df(cond).astype(bool)
    a = a if isinstance(a, pd.DataFrame) else pd.DataFrame(a, index=cond.index, columns=cond.columns)
    b = b if isinstance(b, pd.DataFrame) else pd.DataFrame(b, index=cond.index, columns=cond.columns)
    return a.where(cond, b)


# ---------------- time-series (per stock, axis=0; int windows) ----------------
def ts_sum(x, d=10):
    return _df(x).rolling(int(d), min_periods=max(1, int(d) // 2)).sum()


def sma(x, d=10):
    return _df(x).rolling(int(d), min_periods=max(1, int(d) // 2)).mean()


def stddev(x, d=10):
    return _df(x).rolling(int(d), min_periods=max(2, int(d) // 2)).std()


def correlation(x, y, d=10):
    return _df(x).rolling(int(d), min_periods=max(2, int(d) // 2)).corr(_df(y))


def covariance(x, y, d=10):
    return _df(x).rolling(int(d), min_periods=max(2, int(d) // 2)).cov(_df(y))


def ts_min(x, d=10):
    return _df(x).rolling(int(d), min_periods=max(1, int(d) // 2)).min()


def ts_max(x, d=10):
    return _df(x).rolling(int(d), min_periods=max(1, int(d) // 2)).max()


def delta(x, d=1):
    return _df(x).diff(int(d))


def delay(x, d=1):
    return _df(x).shift(int(d))


def _windows(x, d):
    a = _df(x).to_numpy(dtype=float)
    return a, sliding_window_view(a, int(d), axis=0)


def ts_rank(x, d=10):
    x = _df(x); d = int(d)
    a, w = _windows(x, d)
    out = np.full(a.shape, np.nan)
    if a.shape[0] >= d:
        last = w[..., -1][..., None]
        out[d - 1:] = (w < last).sum(-1) + ((w == last).sum(-1) + 1) / 2.0
        out[d - 1:] /= d  # normalize to (0,1] like a percentile rank
    return pd.DataFrame(out, index=x.index, columns=x.columns)


def ts_argmax(x, d=10):
    x = _df(x); d = int(d)
    a, w = _windows(x, d)
    out = np.full(a.shape, np.nan)
    if a.shape[0] >= d:
        out[d - 1:] = np.nan_to_num(w, nan=-np.inf).argmax(-1) + 1
    return pd.DataFrame(out, index=x.index, columns=x.columns)


def ts_argmin(x, d=10):
    x = _df(x); d = int(d)
    a, w = _windows(x, d)
    out = np.full(a.shape, np.nan)
    if a.shape[0] >= d:
        out[d - 1:] = np.nan_to_num(w, nan=np.inf).argmin(-1) + 1
    return pd.DataFrame(out, index=x.index, columns=x.columns)


def product(x, d=10):
    x = _df(x); d = int(d)
    a, w = _windows(x, d)
    out = np.full(a.shape, np.nan)
    if a.shape[0] >= d:
        out[d - 1:] = np.nanprod(w, axis=-1)
    return pd.DataFrame(out, index=x.index, columns=x.columns)


def decay_linear(x, d=10):
    x = _df(x).ffill().bfill().fillna(0.0); d = int(d)
    w = np.arange(1, d + 1, dtype=float)
    w /= w.sum()
    out = None
    for i in range(d):                       # newest day gets the largest weight
        term = x.shift(d - 1 - i) * w[i]
        out = term if out is None else out + term
    return out


# aliases used by the WorldQuant formulas
ts_corr = correlation
ts_cov = covariance
sum_ = ts_sum
mean = sma
stdev = stddev


def adv_builder(volume):
    """Return adv(d) = d-day average daily volume, bound to this panel's volume."""
    def adv(d=20):
        return sma(volume, int(d))
    return adv


# the names exposed to the DSL sandbox (functions only; fields injected per-panel)
OP_NAMES = [
    "rank", "scale", "indneutralize", "log", "sign", "abs_", "signedpower",
    "maximum", "minimum", "iif", "ts_sum", "sma", "stddev", "correlation",
    "covariance", "ts_min", "ts_max", "delta", "delay", "ts_rank", "ts_argmax",
    "ts_argmin", "product", "decay_linear", "ts_corr", "ts_cov", "sum_", "mean",
    "stdev",
]


def op_namespace():
    return {name: globals()[name] for name in OP_NAMES}
