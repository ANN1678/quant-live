"""記録を集計して、サイトが読む形にまとめる。

**関門の考え方**
的中率では決めない。このやり方は外すほうが多くても、勝ったときの値幅が大きければ増えるからだ。
見るのは1回あたりの平均損益（手数料を引いた後）と、その平均が偶然でないと言える件数の2つにする。

  必要な件数 = (1.96 × ばらつき ÷ 平均) の2乗

平均が小さいほど必要な件数は増える。増え方が大きいので、
「わずかにプラス」では何年かかっても決められない。この式をそのままサイトに出す。
"""
from __future__ import annotations

import math
import statistics
from datetime import timedelta

import paper
import strategy
from common import (DATA, EQUITY, PREDICTIONS, SUMMARY, iso, now, read_json,
                    read_jsonl, write_json)

RESULTS = DATA / "results.jsonl"
TRADES = DATA / "trades.jsonl"
POSITIONS = DATA / "positions.json"


def _pred_stats(results: list[dict]) -> dict:
    judged = [r for r in results if r["hit"] is not None]
    hits = sum(1 for r in judged if r["hit"])
    return {
        "judged": len(judged),
        "hits": hits,
        "hit_rate": round(hits / len(judged) * 100, 2) if judged else None,
        "passed": len(results) - len(judged),
    }


def _trade_stats(trades: list[dict]) -> dict:
    if not trades:
        return {"trades": 0, "wins": 0, "win_rate": None, "avg_net_pct": None,
                "sd_pct": None, "win_avg_pct": None, "loss_avg_pct": None,
                "payoff": None, "required_trades": None, "enough": False}
    nets = [t["net_pct"] for t in trades]
    wins = [n for n in nets if n > 0]
    losses = [n for n in nets if n <= 0]
    mean = statistics.mean(nets)
    sd = statistics.stdev(nets) if len(nets) > 1 else 0.0
    required = None
    if mean > 0 and sd > 0:
        required = math.ceil((1.96 * sd / mean) ** 2)
    return {
        "trades": len(trades),
        "wins": len(wins),
        "win_rate": round(len(wins) / len(trades) * 100, 2),
        "avg_net_pct": round(mean, 4),
        "sd_pct": round(sd, 4),
        "win_avg_pct": round(statistics.mean(wins), 3) if wins else None,
        "loss_avg_pct": round(statistics.mean(losses), 3) if losses else None,
        "payoff": round(abs(statistics.mean(wins) / statistics.mean(losses)), 3)
                  if wins and losses and statistics.mean(losses) != 0 else None,
        "required_trades": required,
        "enough": bool(required is not None and len(trades) >= required),
    }


def build() -> dict:
    results = read_jsonl(RESULTS)
    trades = read_jsonl(TRADES)
    preds = read_jsonl(PREDICTIONS)
    n = now()
    done = {r["id"] for r in results}
    pending = [p for p in preds if p["id"] not in done]

    def since(days: int):
        edge = (n - timedelta(days=days)).timestamp() * 1000
        return ([r for r in results if r["target_t"] >= edge],
                [t for t in trades if t["close_t"] >= edge])

    r7, t7 = since(7)
    r30, t30 = since(30)

    capital = paper.START_CAPITAL
    curve, peak, max_dd = [], capital, 0.0
    for t in sorted(trades, key=lambda x: x["close_t"]):
        capital += capital * paper.POSITION * (t["net_pct"] / 100)
        peak = max(peak, capital)
        max_dd = max(max_dd, (peak - capital) / peak * 100)
        curve.append({"t": t["close_t"], "capital": round(capital)})

    tr_all = _trade_stats(trades)
    summary = {
        "generated_at": iso(n),
        "model": strategy.MODEL,
        "horizon_hours": strategy.HORIZON_HOURS,
        "made": len(preds),
        "open_positions": [v for v in (read_json(POSITIONS, {}) or {}).values() if v],
        "pending": [
            {k: p[k] for k in ("id", "pair", "direction", "confidence", "base_price",
                               "target_at", "made_at", "model")}
            for p in sorted(pending, key=lambda x: x["target_t"])[-8:]
        ],
        "predictions": {
            "all": _pred_stats(results),
            "last_7d": _pred_stats(r7),
            "last_30d": _pred_stats(r30),
            "per_pair": {p: _pred_stats([r for r in results if r["pair"] == p])
                         for p in sorted({r["pair"] for r in results})},
        },
        "trading": {
            "all": tr_all,
            "last_7d": _trade_stats(t7),
            "last_30d": _trade_stats(t30),
            "per_pair": {p: _trade_stats([t for t in trades if t["pair"] == p])
                         for p in sorted({t["pair"] for t in trades})},
        },
        "gate": {
            "rule": "1回あたりの平均損益が、手数料を引いた後でプラスであること。"
                    "それを偶然では説明できない件数で示すこと。",
            "avg_net_pct": tr_all["avg_net_pct"],
            "trades": tr_all["trades"],
            "required_trades": tr_all["required_trades"],
            "cleared": tr_all["enough"] and (tr_all["avg_net_pct"] or 0) > 0,
        },
        "capital": {
            "start": paper.START_CAPITAL,
            "now": round(capital),
            "change_pct": round((capital / paper.START_CAPITAL - 1) * 100, 3),
            "max_drawdown_pct": round(max_dd, 3),
        },
        "assumptions": {
            "fee_pct": round(paper.FEE * 100, 4),
            "slippage_pct": round(paper.SLIPPAGE * 100, 4),
            "round_trip_cost_pct": round(paper.ROUND_TRIP_COST * 100, 4),
            "position_pct": round(paper.POSITION * 100, 2),
        },
    }
    write_json(SUMMARY, summary)
    write_json(EQUITY, {"start": paper.START_CAPITAL, "curve": curve})
    return summary
