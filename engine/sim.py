"""本番と同じ規則を、過去の足に当てはめる模擬売買。backtest.py が使う。

本番（run.py）との違いは1つだけ。本番は run の時点の気配で約定したことにするが、過去には気配の記録が無いので、
**その足の終値**で約定したことにする。差は実測で1件あたり ±0.1〜0.3% のぶれ（期待値の偏りは無い）。

規則（run.py と同じ順番）
  1. 判定  2. 予測  3. 期限の来た玉を、予測が同じ向きなら持ち越し、違えば手仕舞う  4. 玉が無く「上」なら建てる
"""
from __future__ import annotations

from common import HOUR_MS
import paper
import strategy


def _sign(x: float) -> int:
    return 1 if x > 0 else -1 if x < 0 else 0


def simulate(pair: str, candles: list[dict], decide=strategy.decide, *, H: int = strategy.HORIZON_HOURS,
             position: float = paper.POSITION, start: float = paper.START_CAPITAL,
             trade_directions=paper.TRADE_DIRECTIONS, window: int = strategy.NEED_HOURS + 8) -> dict:
    """閉じた足（古い順）に規則を当てる。返り値: 予測の判定・区間ごとの売買・資金曲線。"""
    n = len(candles)
    closes = [c["c"] for c in candles]
    gaps = sum(1 for a, b in zip(candles, candles[1:]) if b["t"] - a["t"] != HOUR_MS)
    if gaps:
        print(f"::warning::{pair}: 1時間おきでない足の継ぎ目が {gaps} か所。区間の長さが 72 時間からずれる")
    calls = [None] * n
    for i in range(n):
        call = decide(candles[max(0, i - window): i + 1])
        calls[i] = call["direction"] if call else None

    # 予測の判定（毎時。重なる）
    judged = hits = 0
    per_dir = {"up": [0, 0], "down": [0, 0]}
    nonoverlap = [0, 0]
    first_judged = None
    for i in range(n - H):
        d = calls[i]
        if d in (None, "none"):
            continue
        fwd = _sign(closes[i + H] - closes[i])
        hit = (fwd > 0 and d == "up") or (fwd < 0 and d == "down")
        judged += 1; hits += int(hit)
        per_dir[d][0] += 1; per_dir[d][1] += int(hit)
        if first_judged is None:
            first_judged = i
        if (i - first_judged) % H == 0:
            nonoverlap[0] += 1; nonoverlap[1] += int(hit)

    # 売買（重ならない。1玉。持ち越しあり）
    trades: list[dict] = []
    pos = None
    capital = start
    peak, max_dd = capital, 0.0
    curve: list[dict] = []

    def record(exit_idx: int, closes_now: bool) -> None:
        nonlocal capital, peak, max_dd
        c_exit = closes[exit_idx]
        pnl = paper.settle(pair, pos["dir"], pos["entry"], c_exit, candles[pos["entry_idx"]]["t"],
                           candles[exit_idx]["t"], opens=(pos["seg"] == 1), closes=closes_now)
        capital += capital * position * (pnl["net_pct"] / 100)
        peak = max(peak, capital)
        max_dd = max(max_dd, (peak - capital) / peak * 100)
        trades.append({
            "pair": pair, "direction": pos["dir"], "seg": pos["seg"],
            "open_t": candles[pos["entry_idx"]]["t"], "close_t": candles[exit_idx]["t"],
            "entry": pos["entry"], "exit": c_exit, "hours": exit_idx - pos["entry_idx"],
            "opens": pos["seg"] == 1, "closes": closes_now,
            "hit": (c_exit > pos["entry"]) if pos["dir"] == "up" else (c_exit < pos["entry"]),
            **pnl,
        })
        curve.append({"t": candles[exit_idx]["t"], "capital": round(capital)})

    for i in range(n):
        d = calls[i]
        if pos is not None and i >= pos["exit_idx"]:
            if d == pos["dir"] and d in trade_directions and i + H < n:
                record(i, closes_now=False)
                pos["entry"] = closes[i]; pos["entry_idx"] = i; pos["exit_idx"] = i + H; pos["seg"] += 1
            else:
                record(i, closes_now=True)
                pos = None
        if pos is None and d in trade_directions and i + H < n:
            pos = {"dir": d, "entry": closes[i], "entry_idx": i, "exit_idx": i + H, "seg": 1}

    return {
        "judged": judged, "hits": hits,
        "hit_rate": round(hits / judged * 100, 2) if judged else None,
        "judged_nonoverlap": nonoverlap[0],
        "hit_rate_nonoverlap": round(nonoverlap[1] / nonoverlap[0] * 100, 2) if nonoverlap[0] else None,
        "up_judged": per_dir["up"][0], "up_hit_rate": round(per_dir["up"][1] / per_dir["up"][0] * 100, 2) if per_dir["up"][0] else None,
        "down_judged": per_dir["down"][0], "down_hit_rate": round(per_dir["down"][1] / per_dir["down"][0] * 100, 2) if per_dir["down"][0] else None,
        "passed": sum(1 for d in calls if d == "none"),
        "trades": trades, "capital_end": capital, "max_drawdown_pct": round(max_dd, 3), "curve": curve,
    }


def always_up(candles: list[dict]) -> dict | None:
    """比較の基準。いつでも「上」と言う。ロングだけの規則では『常時ロング』になる。
    戦略と同じ助走（28日）が揃うまでは None を返し、同じ期間で比べる。"""
    if not candles or candles[-1]["t"] - candles[0]["t"] < strategy.NEED_HOURS * HOUR_MS:
        return None
    return {"model": "always-up", "horizon_hours": strategy.HORIZON_HOURS, "direction": "up", "confidence": None, "reason": {}}
