"""key=execution: ema-cross-v1 の信号はそのまま。約定とコストの側だけ変える。

信号 = ema-cross-v1（EMA12/48、ATR24、見送り線 0.15×ATR）と同じ計算。
建てる条件 = direction が up で、confidence が上限の 0.85（|spread|/width >= 2.0）のときだけ。
   本番の decide() は strength = min(|spread|/width, 2.0)、confidence = 0.50 + 0.175×strength。
   つまり「自信が上限に張り付いた上向きだけ」。パラメータを足していない（既存の上限 2.0 を使う）。
ショートは建てない（建玉管理料 0.04%/日を払わない。踏み上げの危険も無い）。
約定 = 指値。終値に置いて、次の足がその値を突き抜けたら約定（メイカー -0.02%、すべり 0）。
   突き抜けなければその足は建てない（次の足でまた判定）。手仕舞いも同じで、だめなら次の足の始値で成行。
   ⚠ 指値の前提は楽観的。必ず fill='next_open' の数字も並べる。
H = 72 時間。hold_through は使わない（指値ならコストが無いので建て直しで失うものが少ない）。
"""
from __future__ import annotations
import numpy as np
import pandas as pd

FAST, SLOW, ATR_N, QUIET = 12, 48, 24, 0.15
STRENGTH_MIN = 2.0  # decide() の strength の上限そのもの（confidence 0.85）

CONFIG = dict(H=72, fill="limit", hold_through=False, position=0.10, costs="DEFAULT_COSTS")
PARAMS = dict(fast=FAST, slow=SLOW, atr_n=ATR_N, quiet=QUIET, strength_min=STRENGTH_MIN, long_only=True)


def _ema_tail(c: np.ndarray, n: int) -> np.ndarray:
    """本番の ema(closes[-3n:], n) を全足で。足 i は c[:i+1] の末尾 3n 本を使い、先頭の値で初期化する。"""
    W = 3 * n
    k = 2 / (n + 1)
    w = k * (1 - k) ** np.arange(W)
    w[W - 1] = (1 - k) ** (W - 1)
    out = np.full(len(c), np.nan)
    if len(c) >= W:
        out[W - 1:] = np.convolve(c, w, mode="valid")
    for i in range(min(W - 1, len(c))):
        e = c[0]
        for v in c[1: i + 1]:
            e = v * k + e * (1 - k)
        out[i] = e
    return out


def _atr_width(df: pd.DataFrame, n: int) -> np.ndarray:
    h = df["h"].to_numpy(); l = df["l"].to_numpy(); c = df["c"].to_numpy()
    tr = np.full(len(c), np.nan)
    tr[1:] = np.maximum.reduce([h[1:] - l[1:], np.abs(h[1:] - c[:-1]), np.abs(c[:-1] - l[1:])]) / c[1:]
    return pd.Series(tr).rolling(n, min_periods=1).mean().to_numpy()


def strategy(df: pd.DataFrame) -> np.ndarray:
    c = df["c"].to_numpy()
    fast = _ema_tail(c, FAST)
    slow = _ema_tail(c, SLOW)
    width = _atr_width(df, ATR_N)
    spread = (fast - slow) / slow
    n = len(c)
    sig = np.zeros(n, dtype=int)
    ok = (width > 0) & (np.abs(spread) >= QUIET * width) & (np.abs(spread) >= STRENGTH_MIN * width)
    sig[ok & (spread > 0)] = 1
    sig[: SLOW + 1] = 0  # 本番は len(candles) >= SLOW+2 から
    return sig
