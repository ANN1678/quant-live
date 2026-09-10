"""tsmom-daily-v1: 日次スケールの時系列モメンタム（Moskowitz–Ooi–Pedersen 2012 / Liu–Tsyvinski 2021）。

信号（毎時、閉じた 1 時間足の終値だけ）
  r_N = c[i] / c[i - 24N] - 1  (N = 7, 14, 28 日)
  方向 = 3 つの符号の多数決。ゼロ割れ（票が 0）なら見送り
大きさ（Harvey ほか 2018 のボラ目標）
  size = min(1.0, 0.02 / 実現日次ボラ)、実現ボラ = 直近 20 本の重ならない 24 時間リターンの標本標準偏差
保有
  H = 168 時間、hold_through=True（手仕舞い時刻に方向が同じなら建て直さずに延ばす）
必要な足: 24*28 + 1 = 673 本（既定の warmup 720 本に収まる）
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from harness import DEFAULT_COSTS

LOOKBACK_DAYS = (7, 14, 28)
VOL_DAYS = 20
TARGET_VOL = 0.02
SIZE_CAP = 1.0

CONFIG = dict(H=168, fill="next_open", hold_through=True, position=0.10, costs=DEFAULT_COSTS)


def _lagged_returns(c: np.ndarray, hours: int) -> np.ndarray:
    r = np.full(len(c), np.nan)
    if len(c) > hours:
        r[hours:] = c[hours:] / c[:-hours] - 1.0
    return r


def _realized_daily_vol(c: np.ndarray, n_days: int) -> np.ndarray:
    n = len(c)
    out = np.full(n, np.nan)
    r24 = _lagged_returns(c, 24)
    for i in range(24 * n_days, n):
        out[i] = np.std(r24[i - 24 * np.arange(n_days)], ddof=1)
    return out


def strategy(df: pd.DataFrame):
    c = df["c"].to_numpy(dtype=float)
    n = len(c)
    votes = np.zeros(n)
    valid = np.ones(n, dtype=bool)
    for N in LOOKBACK_DAYS:
        r = _lagged_returns(c, 24 * N)
        valid &= ~np.isnan(r)
        votes += np.sign(np.nan_to_num(r))
    sig = np.where(valid, np.sign(votes), 0.0).astype(int)
    vol = _realized_daily_vol(c, VOL_DAYS)
    size = np.where(np.isnan(vol) | (vol <= 0), 1.0, np.minimum(SIZE_CAP, TARGET_VOL / np.where(vol > 0, vol, 1.0)))
    size = np.where(valid, size, 0.0)
    return sig, size
