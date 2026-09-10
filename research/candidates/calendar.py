"""calendar-window-v1: 時間帯の季節性だけで動く。

毎日 21:00 UTC（06:00 JST）の足が閉じたら「上」と言い、22:00 UTC の始値で買って 6 時間後（04:00 UTC = 13:00 JST）に売る。
それ以外の時刻は見送り。パラメータは窓の位置だけで、train の前半（2022-09〜2023-12）の時間帯別 1h 収益率から決め、
後半（2024-01〜2025-03）でも同じ符号で残ることを確かめた。

⚠ 成行（テイカー 0.12%＋すべり 0.05% 片道）では負ける。窓の値幅（約 +0.15%/6h）が往復 0.34% に届かない。
   指値（メイカー -0.02%）で約定した場合だけ薄くプラス。CONFIG の fill='limit' はその楽観的な前提を含む。
   本番へ出す前に next_open の数字（マイナス）も必ず並べること。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # research/ を足す（candidates/ は足さない: この file は stdlib calendar と同名）
from harness import DEFAULT_COSTS

DECIDE_HOUR_UTC = 21   # この足の終値で決める（22:00 UTC の始値で建つ）
HORIZON_HOURS = 6      # 04:00 UTC の始値で手仕舞う

CONFIG = dict(H=HORIZON_HOURS, fill="limit", hold_through=False, position=0.10, costs=DEFAULT_COSTS)


def strategy(df: pd.DataFrame) -> np.ndarray:
    """足 i の値は足 i の時刻だけで決まる。価格は見ない（先読みは構造上あり得ない）。"""
    hr = df.index.hour.to_numpy()
    return (hr == DECIDE_HOUR_UTC).astype(int)


def decide_pure(ts_ms: int) -> str:
    """本番用の骨格（純 Python）。最後に閉じた足の開始時刻（ms, UTC）を渡す。"""
    hour_utc = (ts_ms // 3_600_000) % 24
    return "up" if hour_utc == DECIDE_HOUR_UTC else "none"
