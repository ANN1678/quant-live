#!/Users/i2/.pyenv/versions/3.11.4/bin/python3
"""1時間に1回これを走らせる。順番は、決済してから、予測する。

  1. 相場を取る
  2. 判定の時刻を過ぎた予測を、結果で確定する
  3. 期限の来た玉を手仕舞う
  4. 次の72時間を予測して、**結果より先に**書き残す
  5. 玉を持っていなければ建てる（1銘柄1玉まで）
  6. 集計し直す

⚠ 4を2より先にやってはいけない。結果を見てから予測を書ける形にすると、記録の意味が消える。
⚠ predictions.jsonl と results.jsonl と trades.jsonl は追記だけにする。書き換えない。
   git の履歴が「いつ書いたか」の証明になっている。上書きすると証明が消える。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import market
import paper
import strategy
from common import (JST, MARKET, PREDICTIONS, append_jsonl, iso, now, read_json,
                    read_jsonl, write_json)
from report import POSITIONS, RESULTS, TRADES

HOUR_MS = 3_600_000
HORIZON_MS = strategy.HORIZON_HOURS * HOUR_MS


def hour_start_ms(dt: datetime) -> int:
    return int(dt.replace(minute=0, second=0, microsecond=0).timestamp() * 1000)


def at(ms: int) -> str:
    return iso(datetime.fromtimestamp(ms / 1000, JST))


def run() -> None:
    n = now()
    this_hour = hour_start_ms(n)
    preds = read_jsonl(PREDICTIONS)
    settled = {r["id"] for r in read_jsonl(RESULTS)}
    positions = read_json(POSITIONS, {}) or {}
    snapshot = {"generated_at": iso(n), "pairs": {}}

    for pair in market.PAIRS:
        # 72時間ぶんの足に、平均を出すための助走を足して取る。
        candles = market.candles(pair, "1hour", days=10)
        by_t = {c["t"]: c for c in candles}
        closed = [c for c in candles if c["t"] < this_hour]
        if not closed:
            print(f"[skip] {pair}: 終わった足が無い")
            continue

        # --- 2. 予測の判定 ---
        for p in preds:
            if p["pair"] != pair or p["id"] in settled:
                continue
            target = by_t.get(p["target_t"])
            if target is None or p["target_t"] >= this_hour:
                continue
            hit = None
            if p["direction"] != "none":
                up = target["c"] > p["base_price"]
                hit = (up and p["direction"] == "up") or (not up and p["direction"] == "down")
            append_jsonl(RESULTS, {
                "id": p["id"], "pair": pair, "target_t": p["target_t"],
                "target_at": p["target_at"], "direction": p["direction"],
                "confidence": p["confidence"], "model": p["model"],
                "base_price": p["base_price"], "target_price": target["c"],
                "move_pct": round((target["c"] - p["base_price"]) / p["base_price"] * 100, 4),
                "hit": hit, "settled_at": iso(n),
            })
            settled.add(p["id"])
            print(f"[判定] {p['id']} {p['direction']} 的中={hit}")

        # --- 3. 手仕舞い ---
        pos = positions.get(pair)
        if pos:
            exit_candle = by_t.get(pos["close_t"])
            if exit_candle is not None and pos["close_t"] < this_hour:
                pnl = paper.settle(pos["direction"], pos["entry"], exit_candle["c"])
                up = exit_candle["c"] > pos["entry"]
                append_jsonl(TRADES, {
                    "id": pos["id"], "pair": pair, "model": pos["model"],
                    "direction": pos["direction"],
                    "open_t": pos["open_t"], "open_at": at(pos["open_t"]),
                    "close_t": pos["close_t"], "close_at": at(pos["close_t"]),
                    "entry": pos["entry"], "exit": exit_candle["c"],
                    "hit": (up and pos["direction"] == "up") or (not up and pos["direction"] == "down"),
                    **pnl,
                })
                print(f"[手仕舞い] {pos['id']} 手数料後 {pnl['net_pct']}%")
                positions[pair] = None
                pos = None

        # --- 4. 予測 ---
        base = closed[-1]
        target_t = base["t"] + HORIZON_MS
        pid = f"{pair}-{base['t']}"
        call = None
        if not any(p["id"] == pid for p in preds):
            call = strategy.decide([c for c in candles if c["t"] <= base["t"]])
            if call is None:
                print(f"[skip] {pair}: 足が足りない")
            else:
                row = {"id": pid, "pair": pair, "made_at": iso(n),
                       "base_t": base["t"], "base_at": at(base["t"]),
                       "base_price": base["c"], "target_t": target_t,
                       "target_at": at(target_t), **call}
                append_jsonl(PREDICTIONS, row)
                preds.append(row)
                print(f"[予測] {pid} {call['direction']} 自信={call['confidence']}")

        # --- 5. 建てる ---
        if pos is None and call and call["direction"] != "none":
            positions[pair] = {
                "id": pid, "pair": pair, "model": call["model"],
                "direction": call["direction"], "confidence": call["confidence"],
                "open_t": base["t"], "open_at": at(base["t"]),
                "close_t": target_t, "close_at": at(target_t),
                "entry": base["c"],
            }
            print(f"[建てる] {pair} {call['direction']} @{base['c']:,.0f}")

        t = market.ticker(pair)
        held = positions.get(pair)
        if held:
            raw = (t["last"] - held["entry"]) / held["entry"]
            if held["direction"] == "down":
                raw = -raw
            held["unrealized_pct"] = round((raw - paper.ROUND_TRIP_COST) * 100, 3)
        snapshot["pairs"][pair] = {
            "ticker": t,
            "position": held,
            "candles": [{"t": c["t"], "c": c["c"]} for c in candles[-120:]],
        }

    write_json(POSITIONS, positions)
    write_json(MARKET, snapshot)

    import report
    s = report.build()
    g = s["gate"]
    print(f"[集計] 予測 {s['made']}件／判定 {s['predictions']['all']['judged']}件"
          f"／的中率 {s['predictions']['all']['hit_rate']}"
          f"／売買 {g['trades']}件／平均 {g['avg_net_pct']}%／必要 {g['required_trades']}件")


if __name__ == "__main__":
    run()
