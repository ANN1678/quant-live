"""crossasset: 市場全体の幅（breadth）で決める。ロングのみ。

規則（足 i の終値で決める）
  5銘柄（btc, eth, xrp, ltc, doge の各 /jpy）それぞれについて「終値 > 48時間EMA」を数える。
  5銘柄すべてが上なら +1（上）。それ以外は 0（見送り）。下は言わない（ショートは訓練期間で一貫して負けた）。
  建玉は72時間。期限が来たとき signal がまだ +1 なら閉じずに72時間延ばす（hold_through）。

パラメータは2つ: EMA_N=48（既存モデルの SLOW と同じ値）、NEED=5（全銘柄一致）。
他銘柄の終値は df.index に合わせて切るので、df の最後の足より先は見えない。
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))  # research/ (harness.py, cache/)
from harness import load, DEFAULT_COSTS  # noqa: E402

PAIRS = ["btc_jpy", "eth_jpy", "xrp_jpy", "ltc_jpy", "doge_jpy"]
EMA_N = 48
NEED = 5
CONFIG = dict(H=72, fill="next_open", hold_through=True, position=0.10, costs=DEFAULT_COSTS)

_PANEL: pd.DataFrame | None = None


def _panel() -> pd.DataFrame:
    global _PANEL
    if _PANEL is None:
        _PANEL = pd.DataFrame({p: load(p)["c"] for p in PAIRS})
    return _PANEL


def strategy(df: pd.DataFrame) -> np.ndarray:
    P = _panel().reindex(df.index).ffill()          # df の最後の足より先の行は入らない
    ema = P.ewm(span=EMA_N, adjust=False).mean()    # k = 2/(N+1)、先頭の値で始める（本番の ema() と同じ漸化式）
    above = (P > ema).sum(axis=1)
    sig = np.zeros(len(df), dtype=int)
    sig[(above >= NEED).to_numpy()] = 1
    sig[P.isna().any(axis=1).to_numpy()] = 0
    return sig
