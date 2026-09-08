#!/Users/i2/.pyenv/versions/3.11.4/bin/python3
"""同じやり方を過去の足に当てはめて、素性を見る。

⚠ **これは予測の記録ではない。** 過去のデータを後から通しただけで、事前に公開していない。
   サイトでも別の場所に、別の名前で出す。混ぜたら全部が疑わしくなる。

本番と同じ規則で回す。予測は1時間ごと（重なる）。玉は1銘柄1つまでで、72時間持つ。
"""
from __future__ import annotations

import math
import statistics
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import market
import paper
import strategy
from common import BACKTEST, JST, iso, now, write_json

DAYS = 90
H = strategy.HORIZON_HOURS


def run_pair(pair: str, days: int = DAYS) -> dict:
    candles = market.candles(pair, "1hour", days=days)
    judged = hits = 0
    trades: list[dict] = []
    curve: list[dict] = []
    capital = paper.START_CAPITAL
    peak, max_dd = capital, 0.0
    next_free = 0  # この足まで玉を持っている

    for i in range(strategy.SLOW + 2, len(candles) - H):
        window = candles[: i + 1]
        call = strategy.decide(window)
        if call is None:
            continue
        entry = window[-1]["c"]
        exit_ = candles[i + H]["c"]

        # 予測の判定（重なる。1時間ごとに全部数える）
        if call["direction"] != "none":
            judged += 1
            up = exit_ > entry
            if (up and call["direction"] == "up") or (not up and call["direction"] == "down"):
                hits += 1

        # 売買（重ならない。玉が空いているときだけ建てる）
        if call["direction"] != "none" and i >= next_free:
            pnl = paper.settle(call["direction"], entry, exit_)
            capital += capital * paper.POSITION * (pnl["net_pct"] / 100)
            peak = max(peak, capital)
            max_dd = max(max_dd, (peak - capital) / peak * 100)
            trades.append(pnl)
            curve.append({"t": candles[i + H]["t"], "capital": round(capital)})
            next_free = i + H

    nets = [t["net_pct"] for t in trades]
    wins = [x for x in nets if x > 0]
    losses = [x for x in nets if x <= 0]
    mean = statistics.mean(nets) if nets else None
    sd = statistics.stdev(nets) if len(nets) > 1 else None
    required = math.ceil((1.96 * sd / mean) ** 2) if mean and sd and mean > 0 else None

    return {
        "pair": pair,
        "from": iso(datetime.fromtimestamp(candles[0]["t"] / 1000, JST)),
        "to": iso(datetime.fromtimestamp(candles[-1]["t"] / 1000, JST)),
        "hours": len(candles),
        "judged": judged,
        "hits": hits,
        "hit_rate": round(hits / judged * 100, 2) if judged else None,
        "trades": len(trades),
        "wins": len(wins),
        "win_rate": round(len(wins) / len(trades) * 100, 2) if trades else None,
        "avg_net_pct": round(mean, 4) if mean is not None else None,
        "sd_pct": round(sd, 4) if sd is not None else None,
        "win_avg_pct": round(statistics.mean(wins), 3) if wins else None,
        "loss_avg_pct": round(statistics.mean(losses), 3) if losses else None,
        "required_trades": required,
        "capital_end": round(capital),
        "change_pct": round((capital / paper.START_CAPITAL - 1) * 100, 3),
        "max_drawdown_pct": round(max_dd, 3),
        "curve": curve,
    }


if __name__ == "__main__":
    out = {
        "generated_at": iso(now()),
        "model": strategy.MODEL,
        "horizon_hours": H,
        "days": DAYS,
        "warning": "過去の足に後から当てはめた結果です。事前に公開した予測ではありません。",
        "assumptions": {
            "fee_pct": round(paper.FEE * 100, 4),
            "slippage_pct": round(paper.SLIPPAGE * 100, 4),
            "round_trip_cost_pct": round(paper.ROUND_TRIP_COST * 100, 4),
            "position_pct": round(paper.POSITION * 100, 2),
        },
        "pairs": {},
    }
    for p in market.PAIRS:
        r = run_pair(p)
        out["pairs"][p] = r
        print(f"{p}: 予測 {r['judged']}件・的中率 {r['hit_rate']}% ／ "
              f"売買 {r['trades']}件・平均 {r['avg_net_pct']}%・"
              f"必要件数 {r['required_trades']} ／ 資金 {r['change_pct']}%・最大下落 {r['max_drawdown_pct']}%")
    write_json(BACKTEST, out)
