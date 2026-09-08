"""仮想の売買。約定したことにする前提を、1か所に集める。

⚠ この数字を甘くすると、サイト全体が嘘になる。緩めるときは /method/ の表も同時に直す。
"""
from __future__ import annotations

# bitbank の成行（テイカー）手数料。片道 0.12%。
FEE = 0.0012
# 板を叩いたときのずれ。片道 0.05% を引く。
SLIPPAGE = 0.0005
# 1回の建玉に使う資金の割合。
POSITION = 0.10
# 出発点の資金（円）。
START_CAPITAL = 1_000_000

ROUND_TRIP_COST = (FEE + SLIPPAGE) * 2  # 往復 0.34%


def settle(direction: str, entry: float, exit_: float) -> dict:
    """建てて手仕舞うまでを1件ぶん計算する。手数料とずれを引いた後の値を返す。"""
    raw = (exit_ - entry) / entry
    if direction == "down":
        raw = -raw
    net = raw - ROUND_TRIP_COST
    return {
        "gross_pct": round(raw * 100, 4),
        "cost_pct": round(ROUND_TRIP_COST * 100, 4),
        "net_pct": round(net * 100, 4),
    }
