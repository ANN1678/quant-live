"""候補 breakout: 20日チャネルの更新に ATR の余白を付けたブレイクアウト（donchian-atr-v1）。

決め方（足 i の終値まで）
  up = 過去 N 本（足 i-N .. i-1、足 i は含めない）の高値の最大
  dn = 同じく安値の最小
  atr = 過去 ATR_N 本（足 i-ATR_N+1 .. i）の真の値幅（TR）の単純平均
  終値 c[i] > up + K*atr なら +1（上）、c[i] < dn - K*atr なら -1（下）、どちらでもなければ 0（見送り）
  信号は更新した足だけに立つ（インパルス）。建玉があるあいだは無視される。H 時間後に手仕舞い、同じ足で次の判定に戻る。

パラメータ: N=480（20日）, K=1.0, ATR_N=24, H=72。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

N = 480
K = 1.0
ATR_N = 24

CONFIG = dict(H=72, fill="next_open", hold_through=False, position=0.10, costs=None)  # costs=None → harness の DEFAULT_COSTS


def strategy(df: pd.DataFrame) -> np.ndarray:
    h, l, c = df["h"], df["l"], df["c"]
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = tr.rolling(ATR_N, min_periods=ATR_N).mean()
    up = h.shift(1).rolling(N, min_periods=N).max()
    dn = l.shift(1).rolling(N, min_periods=N).min()
    sig = np.zeros(len(df), dtype=int)
    sig[(c > up + K * atr).to_numpy()] = 1
    sig[(c < dn - K * atr).to_numpy()] = -1
    return sig


def decide_pure(candles: list[dict]) -> str:
    """本番 engine/strategy.py 用の純 Python 版（numpy 無し）。candles は古い順、最後が直近の閉じた足。
    返り値 'up' / 'down' / 'none'。N+1 本以上の足が要る。"""
    if len(candles) < N + 1:
        return "none"
    last = candles[-1]
    window = candles[-N - 1:-1]  # 直近の足を除く N 本
    up = max(x["h"] for x in window)
    dn = min(x["l"] for x in window)
    tail = candles[-ATR_N - 1:]  # TR の計算に前の足の終値が要るので ATR_N+1 本
    trs = []
    for prev, cur in zip(tail[:-1], tail[1:]):
        trs.append(max(cur["h"] - cur["l"], abs(cur["h"] - prev["c"]), abs(cur["l"] - prev["c"])))
    if len(trs) < ATR_N:
        return "none"
    atr = sum(trs) / len(trs)
    if last["c"] > up + K * atr:
        return "up"
    if last["c"] < dn - K * atr:
        return "down"
    return "none"
