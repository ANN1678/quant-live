"""成績の数え方。report.py（本番の記録）と backtest.py（過去への当てはめ）が同じ関数を使う。

数字の意味
- mean / sd     : 1件あたりの net% の平均と標本標準偏差
- t             : 平均 ÷ 標準偏差 × √件数。0 から何σ離れているか
- ci95          : 平均のブートストラップ 95% 区間（2000回、種は固定）。裾が厚い分布でも使える
- median        : 中央値。少数の大勝ちに引っ張られない
- trimmed_mean  : 最大と最小を1件ずつ除いた平均
- required      : いまの平均と標準偏差が続いた場合に、関門の線（t=2.36）に達する件数の**見込み**。目標ではない
"""
from __future__ import annotations

import math
import random
import statistics


def _empty() -> dict:
    return {"trades": 0, "wins": 0, "win_rate": None, "avg_net_pct": None, "median_net_pct": None,
            "trimmed_mean_pct": None, "sd_pct": None, "t": None, "t_raw": None, "ci95": None, "win_avg_pct": None,
            "loss_avg_pct": None, "payoff": None, "profit_factor": None, "sum_net_pct": None,
            "required_trades": None}


def bootstrap_ci(values: list[float], reps: int = 2000, seed: int = 0) -> tuple[float, float] | None:
    n = len(values)
    if n < 5:
        return None
    rng = random.Random(seed)
    means = []
    for _ in range(reps):
        s = 0.0
        for _ in range(n):
            s += values[rng.randrange(n)]
        means.append(s / n)
    means.sort()
    lo = means[int(0.025 * reps)]
    hi = means[min(reps - 1, int(0.975 * reps))]
    return (round(lo, 4), round(hi, 4))


def trade_stats(nets: list[float], with_ci: bool = True, threshold: float = 2.36) -> dict:
    """threshold は required（見込み件数）の線。関門と同じ 2.36 を既定にする。"""
    n = len(nets)
    if n == 0:
        return _empty()
    mean = statistics.mean(nets)
    sd = statistics.stdev(nets) if n > 1 else None
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x <= 0]
    t = (mean / sd * math.sqrt(n)) if sd else None
    required = math.ceil((threshold * sd / mean) ** 2) if sd and mean > 0 else None
    trimmed = statistics.mean(sorted(nets)[1:-1]) if n >= 3 else mean
    return {
        "trades": n,
        "wins": len(wins),
        "win_rate": round(len(wins) / n * 100, 2),
        "avg_net_pct": round(mean, 4),
        "median_net_pct": round(statistics.median(nets), 4),
        "trimmed_mean_pct": round(trimmed, 4),
        "sd_pct": round(sd, 4) if sd is not None else None,
        "t": round(t, 3) if t is not None else None,
        "t_raw": t,
        "ci95": bootstrap_ci(nets) if with_ci else None,
        "win_avg_pct": round(statistics.mean(wins), 3) if wins else None,
        "loss_avg_pct": round(statistics.mean(losses), 3) if losses else None,
        "payoff": (round(abs(statistics.mean(wins) / statistics.mean(losses)), 3)
                   if wins and losses and statistics.mean(losses) != 0 else None),
        "profit_factor": (round(sum(wins) / -sum(losses), 3) if losses and sum(losses) < 0 else None),
        "sum_net_pct": round(sum(nets), 3),
        "required_trades": required,
    }


def equity_curve(trades: list[dict], position: float, start: float) -> tuple[list[dict], float, float]:
    """手仕舞い順に資金を複利で足す。返り値は (曲線, 最後の資金, 最大下落%)。"""
    capital = start
    peak, max_dd = capital, 0.0
    curve = []
    for t in sorted(trades, key=lambda x: x["close_t"]):
        capital += capital * position * (t["net_pct"] / 100)
        peak = max(peak, capital)
        max_dd = max(max_dd, (peak - capital) / peak * 100)
        curve.append({"t": t["close_t"], "capital": round(capital)})
    return curve, capital, max_dd
