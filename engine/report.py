"""記録を集計して、サイトが読む形にまとめる。

**関門の考え方（v2）**
的中率では決めない。見るのは、閉じた区間（72時間）ごとの net% の平均が、偶然でなくプラスと言えるかだけ。

  t ＝ 平均 ÷ 標準偏差 × √件数

検査は**銘柄ごとに、件数が 50・100・200・400 に達したときの4回だけ**行い、t ≥ 2.36 なら合格。
毎時 t を見て「最初に線を越えた瞬間」を合格にすると、優位が無くても3〜4割の確率で合格が出る（監査で実測）。
4回に絞って線を 2.36 に上げると、偽陽性は 3% 程度に収まる（Pocock の境界）。
400件で合格しなければ、このモデルは終わり。次のモデルは名前を変えて最初から数える。
検査の結果は gate.jsonl に追記し、後から書き換えない。

「必要件数」は出すが、目標ではない。いまの平均と標準偏差が続いた場合の見込みで、毎時動く。
"""
from __future__ import annotations

import math
from datetime import timedelta

import paper
import stats
import strategy
from common import (EQUITY, GATE, POSITIONS, PREDICTIONS, RESULTS, SUMMARY, TRADES, append_jsonl, at, iso,
                    now, read_json, read_jsonl, write_json)

CHECKPOINTS = (50, 100, 200, 400)
THRESHOLD_T = 2.36


def _pred_stats(results: list[dict]) -> dict:
    judged = [r for r in results if r["hit"] is not None]
    hits = sum(1 for r in judged if r["hit"])
    out = {
        "judged": len(judged),
        "hits": hits,
        "hit_rate": round(hits / len(judged) * 100, 2) if judged else None,
        "passed": len(results) - len(judged),
    }
    for d in ("up", "down"):
        rows = [r for r in judged if r["direction"] == d]
        out[f"{d}_judged"] = len(rows)
        out[f"{d}_hit_rate"] = round(sum(1 for r in rows if r["hit"]) / len(rows) * 100, 2) if rows else None
    # 重ならない数え方：銘柄ごとに、最初の判定から 72 時間おきの1件だけ
    non = []
    for pair in sorted({r["pair"] for r in judged}):
        rows = sorted((r for r in judged if r["pair"] == pair), key=lambda r: r["target_t"])
        if not rows:
            continue
        step = strategy.HORIZON_HOURS * 3_600_000
        first = rows[0]["target_t"]
        non.extend(r for r in rows if (r["target_t"] - first) % step == 0)
    out["nonoverlap_judged"] = len(non)
    out["nonoverlap_hit_rate"] = round(sum(1 for r in non if r["hit"]) / len(non) * 100, 2) if non else None
    return out


def _trade_stats(trades: list[dict], with_ci: bool = True) -> dict:
    st = stats.trade_stats([t["net_pct"] for t in trades], with_ci=with_ci)
    st["carried"] = sum(1 for t in trades if not t.get("closes", True))
    return st


def _gate(trades: list[dict], verdicts: list[dict], n_now) -> dict:
    """銘柄ごとに検査する。決めた件数に達した回だけ gate.jsonl に追記する。"""
    per_pair = {}
    for pair in sorted({t["pair"] for t in trades}):
        rows = sorted((t for t in trades if t["pair"] == pair), key=lambda t: (t["close_t"], t["id"]))
        nets = [t["net_pct"] for t in rows]
        mine = [v for v in verdicts if v["pair"] == pair and v["rule"] == paper.RULE and v.get("model") == strategy.MODEL]
        for N in CHECKPOINTS:
            if len(nets) >= N and not any(v["n"] == N for v in mine):
                st = stats.trade_stats(nets[:N], with_ci=False)
                row = {
                    "pair": pair, "rule": paper.RULE, "model": strategy.MODEL, "n": N,
                    "avg_net_pct": st["avg_net_pct"], "sd_pct": st["sd_pct"], "t": st["t"],
                    "threshold_t": THRESHOLD_T, "passed": bool(st["t_raw"] is not None and st["t_raw"] >= THRESHOLD_T),
                    "first_close_at": rows[0]["close_at"], "last_close_at": rows[N - 1]["close_at"],
                    "at": iso(n_now),
                }
                append_jsonl(GATE, row)
                verdicts.append(row)
                mine.append(row)
        st = stats.trade_stats(nets, with_ci=False)
        nxt = next((N for N in CHECKPOINTS if not any(v["n"] == N for v in mine)), None)
        per_pair[pair] = {
            "trades": len(nets), "avg_net_pct": st["avg_net_pct"], "sd_pct": st["sd_pct"], "t": st["t"],
            "next_checkpoint": nxt,
            "verdicts": [{k: v[k] for k in ("n", "t", "passed", "at")} for v in mine],
            "passed": any(v["passed"] for v in mine),
            "finished": nxt is None,
        }
    return per_pair


def build(failed_pairs: list[str] | None = None) -> dict:
    results = read_jsonl(RESULTS)
    trades = read_jsonl(TRADES)
    preds = read_jsonl(PREDICTIONS)
    verdicts = read_jsonl(GATE)
    n = now()
    done = {r["id"] for r in results}
    pending = [p for p in preds if p["id"] not in done]

    cur_preds = [p for p in preds if p["model"] == strategy.MODEL]
    cur_results = [r for r in results if r["model"] == strategy.MODEL]
    cur_trades = [t for t in trades if t.get("rule") == paper.RULE and t.get("model") == strategy.MODEL]

    def since(days: int):
        edge = (n - timedelta(days=days)).timestamp() * 1000
        return ([r for r in cur_results if r["target_t"] >= edge],
                [t for t in cur_trades if t["close_t"] >= edge])

    r7, t7 = since(7)
    r30, t30 = since(30)

    # 資金は口座1つ。旧規則の売買も同じ口座で数える
    curve, capital, max_dd = stats.equity_curve(trades, paper.POSITION, paper.START_CAPITAL)

    per_pair_gate = _gate(cur_trades, verdicts, n)
    tr_all = _trade_stats(cur_trades)
    remaining = {p: (v["next_checkpoint"] - v["trades"]) for p, v in per_pair_gate.items() if v["next_checkpoint"]}
    next_total = min(remaining.values()) if remaining else (CHECKPOINTS[0] if not per_pair_gate else None)

    legacy_models = sorted({p["model"] for p in preds} - {strategy.MODEL})
    legacy_keys = sorted({f"{t.get('model')}/{t.get('rule', 'close-72h-v1')}" for t in trades}
                         - {f"{strategy.MODEL}/{paper.RULE}"})

    summary = {
        "generated_at": iso(n),
        "model": strategy.MODEL,
        "rule": paper.RULE,
        "horizon_hours": strategy.HORIZON_HOURS,
        "made": len(cur_preds),
        "made_all_models": len(preds),
        "open_positions": [v for v in (read_json(POSITIONS, {}) or {}).values() if v],
        "pending": [
            {k: p.get(k) for k in ("id", "pair", "direction", "confidence", "base_price",
                                   "target_at", "made_at", "model", "reason")}
            for p in sorted(pending, key=lambda x: x["target_t"])[-8:]
        ],
        "predictions": {
            "all": _pred_stats(cur_results),
            "last_7d": _pred_stats(r7),
            "last_30d": _pred_stats(r30),
            "per_pair": {p: _pred_stats([r for r in cur_results if r["pair"] == p])
                         for p in sorted({r["pair"] for r in cur_results})},
        },
        "trading": {
            "all": tr_all,
            "last_7d": _trade_stats(t7, with_ci=False),
            "last_30d": _trade_stats(t30, with_ci=False),
            "per_pair": {p: _trade_stats([t for t in cur_trades if t["pair"] == p])
                         for p in sorted({t["pair"] for t in cur_trades})},
        },
        "legacy": {
            "predictions": {m: _pred_stats([r for r in results if r["model"] == m]) for m in legacy_models},
            "trading": {k: _trade_stats([t for t in trades
                                          if f"{t.get('model')}/{t.get('rule', 'close-72h-v1')}" == k], with_ci=False)
                        for k in legacy_keys},
        },
        "gate": {
            "rule": "銘柄ごとに、閉じた区間の平均損益（手数料を引いた後）の t 値を、件数が 50・100・200・400 に達したときの4回だけ検査する。"
                    "t が 2.36 以上なら合格。400件で合格しなければ、このモデルは終わり。",
            "checkpoints": list(CHECKPOINTS),
            "threshold_t": THRESHOLD_T,
            "per_pair": per_pair_gate,
            "avg_net_pct": tr_all["avg_net_pct"],
            "trades": tr_all["trades"],
            "required_trades": next_total,
            "required_trades_note": "いちばん近い検査まで、あと何件か（銘柄ごとの残りの最小）。統計の見込みは trading.all.required_trades",
            "remaining": remaining,
            "cleared": any(v["passed"] for v in per_pair_gate.values()),
        },
        "capital": {
            "start": paper.START_CAPITAL,
            "now": round(capital),
            "change_pct": round((capital / paper.START_CAPITAL - 1) * 100, 3),
            "max_drawdown_pct": round(max_dd, 3),
        },
        "assumptions": {
            **paper.assumptions(),
            "model": strategy.MODEL,
            "lookback_days": list(strategy.LOOKBACK_DAYS),
            "horizon_hours": strategy.HORIZON_HOURS,
        },
        "last_run": {"at": iso(n), "failed_pairs": failed_pairs or []},
    }
    write_json(SUMMARY, summary)
    write_json(EQUITY, {"start": paper.START_CAPITAL, "curve": curve})
    return summary
