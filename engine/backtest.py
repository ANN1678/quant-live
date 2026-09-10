#!/Users/i2/.pyenv/versions/3.11.4/bin/python3
"""同じやり方を過去の足に当てはめて、素性を見る。

⚠ **これは予測の記録ではない。** 過去のデータを後から通しただけで、事前に公開していない。
   サイトでも別の場所に、別の名前で出す。混ぜたら全部が疑わしくなる。

本番と同じ規則（sim.py）で、取れる限り長く回す。既定は4年。bitbank の1時間足は1日1リクエストなので、
4年で銘柄ごとに約1,460回、数分かかる。
90日だけ見ると、1件の大勝ちで平均の符号が決まる（v1 の +0.22% は 2026-08-18 の1件だった）。
だから期間は長く取り、平均のほかに中央値・ブートストラップの区間・年ごとの値を出す。

比較の基準として「常時ロング」（いつでも「上」と言う）も同じ規則で回す。
ロングだけの規則では、相場が上がった期間はどんな信号でもプラスに見える。信号が足したものはその差で読む。

BACKTEST_DAYS を環境変数で渡すと期間を変えられる。
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import market
import paper
import sim
import stats
import strategy
from common import BACKTEST, HOUR_MS, JST, iso, now, write_json

DAYS = int(os.environ.get("BACKTEST_DAYS", "1460"))
H = strategy.HORIZON_HOURS


def _year(ms: int) -> int:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).year


def _sample(curve: list[dict], limit: int = 400) -> list[dict]:
    if len(curve) <= limit:
        return curve
    step = len(curve) / limit
    return [curve[int(i * step)] for i in range(limit)] + [curve[-1]]


def run_pair(pair: str, days: int = DAYS, candles: list[dict] | None = None) -> dict:
    if candles is None:
        candles = market.candles(pair, "1hour", days=days)
    this_hour = int(now().replace(minute=0, second=0, microsecond=0).timestamp() * 1000)
    candles = [c for c in candles if c["t"] < this_hour]  # 形成中の足を除く
    r = sim.simulate(pair, candles)
    base = sim.simulate(pair, candles, decide=sim.always_up)
    nets = [t["net_pct"] for t in r["trades"]]
    st = stats.trade_stats(nets)
    by_year = {}
    for y in sorted({_year(t["close_t"]) for t in r["trades"]}):
        ys = stats.trade_stats([t["net_pct"] for t in r["trades"] if _year(t["close_t"]) == y], with_ci=False)
        by_year[str(y)] = {k: ys[k] for k in ("trades", "avg_net_pct", "sd_pct", "t", "win_rate")}
    bst = stats.trade_stats([t["net_pct"] for t in base["trades"]], with_ci=False)
    return {
        "pair": pair,
        "from": iso(datetime.fromtimestamp(candles[0]["t"] / 1000, JST)),
        "to": iso(datetime.fromtimestamp(candles[-1]["t"] / 1000, JST)),
        "hours": len(candles),
        # 予測（毎時。重なる）
        "judged": r["judged"], "hits": r["hits"], "hit_rate": r["hit_rate"],
        "judged_nonoverlap": r["judged_nonoverlap"], "hit_rate_nonoverlap": r["hit_rate_nonoverlap"],
        "up_judged": r["up_judged"], "up_hit_rate": r["up_hit_rate"],
        "down_judged": r["down_judged"], "down_hit_rate": r["down_hit_rate"],
        "passed": r["passed"],
        # 売買（重ならない。持ち越しの区間も1件）
        **{k: st[k] for k in ("trades", "wins", "win_rate", "avg_net_pct", "median_net_pct", "trimmed_mean_pct",
                               "sd_pct", "t", "ci95", "win_avg_pct", "loss_avg_pct", "payoff", "profit_factor",
                               "required_trades")},
        "carried": sum(1 for t in r["trades"] if not t["closes"]),
        "capital_end": round(r["capital_end"]),
        "change_pct": round((r["capital_end"] / paper.START_CAPITAL - 1) * 100, 3),
        "max_drawdown_pct": r["max_drawdown_pct"],
        "by_year": by_year,
        "always_long": {k: bst[k] for k in ("trades", "avg_net_pct", "sd_pct", "t", "win_rate")},
        "curve": _sample(r["curve"]),
    }


def main(days: int = DAYS) -> dict:
    out = {
        "generated_at": iso(now()),
        "model": strategy.MODEL,
        "rule": paper.RULE,
        "horizon_hours": H,
        "days": days,
        "warning": "過去の足に後から当てはめた結果です。事前に公開した予測ではありません。",
        "fill_note": "過去には気配の記録が無いので、その足の終値で約定したことにしています。本番は run の時点の気配で約定します。",
        "assumptions": {**paper.assumptions(), "lookback_days": list(strategy.LOOKBACK_DAYS)},
        "pairs": {},
    }
    for p in market.PAIRS:
        r = run_pair(p, days)
        out["pairs"][p] = r
        print(f"{p}: 予測 {r['judged']}件・的中率 {r['hit_rate']}%（重ならない {r['judged_nonoverlap']}件・{r['hit_rate_nonoverlap']}%）／ "
              f"売買 {r['trades']}件・平均 {r['avg_net_pct']}%・中央値 {r['median_net_pct']}%・t {r['t']}・区間 {r['ci95']} ／ "
              f"常時ロング {r['always_long']['avg_net_pct']}%（t {r['always_long']['t']}）／ "
              f"資金 {r['change_pct']}%・最大下落 {r['max_drawdown_pct']}%")
    write_json(BACKTEST, out)
    return out


if __name__ == "__main__":
    main()
