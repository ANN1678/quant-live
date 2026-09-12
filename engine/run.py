#!/Users/i2/.pyenv/versions/3.11.4/bin/python3
"""1時間に1回これを走らせる。順番は、判定してから、予測する。

  1. 相場を取る（足と気配）
  2. 判定の時刻を過ぎた予測を、結果で確定する
  3. 次の72時間を予測して、**結果より先に**書き残す
  4. 期限の来た玉を、予測が同じ向きなら持ち越し、違えば手仕舞う
  5. 玉を持っていなければ建てる（1銘柄1玉。「上」のときだけ）
  6. 集計し直す

⚠ 3を2より先にやってはいけない。結果を見てから予測を書ける形にすると、記録の意味が消える。
⚠ **約定の値は足の終値で決める（long-carry-v3）。**建ては合図にした足、手仕舞いは期限の足。
   run が何時に走っても同じ値が書かれる。実際に板にあった気配は entry_actual / exit_actual に並べて残す。
   遅れは late_minutes に入る。詳しくは paper.py の頭。
⚠ predictions.jsonl と results.jsonl と trades.jsonl と gate.jsonl は追記だけにする。書き換えない。
   git の履歴が「いつ書いたか」の証明になっている。上書きすると証明が消える。
⚠ 1銘柄が落ちても、もう1銘柄の記録は残す。落ちた銘柄は次の回に判定と手仕舞いをやり直す（どちらも冪等）。
   その回の予測だけは戻らない。空いた穴は埋めない。
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import market
import paper
import strategy
from common import (HOUR_MS, MARKET, POSITIONS, PREDICTIONS, RESULTS, TRADES, append_jsonl, at, iso,
                    jst_midnights, now, read_json, read_jsonl, write_json)

HORIZON_MS = strategy.HORIZON_HOURS * HOUR_MS
# 28日ぶんの助走に、足の欠けと当日ぶんの余裕を足す
WARMUP_DAYS = strategy.NEED_HOURS // 24 + 3
# 期限の足が取れないまま何日たったら、気配で約定したことにするか。予測の判定（7日）と合わせる
GIVE_UP_MS = 7 * 24 * HOUR_MS


def hour_start_ms(dt: datetime) -> int:
    return int(dt.replace(minute=0, second=0, microsecond=0).timestamp() * 1000)


def rule_fill(by_t: dict, t: int, actual: float, this_hour: int, *, old_rule: bool,
              what: str) -> tuple[float | None, str]:
    """規則の約定値を返す。その時刻の足の終値を使う。2つめの返り値は、どちらを使ったかの印。

    ⚠ **足は時刻で決まるので、run が遅れても同じ値になる。**この記録を外の人が bitbank の公開APIで
       検算できるのは、ここが時刻に依らないからで、いちばん守りたい性質。気配に戻してはいけない。
       2026-09-11に気配で書いていて、4時間半の遅れが手仕舞い2件の符号を裏返した。

    old_rule : 前の版（long-carry-v2）の玉。その版の決まりどおり気配で閉じる。台帳を混ぜない
    """
    if old_rule:
        return actual, "ticker"
    c = by_t.get(t)
    if c is not None:
        return c["c"], "candle"
    if t + GIVE_UP_MS < this_hour:
        # 取引所が7日たっても足を返さない。閉じられないまま残すほうが害が大きいので、気配で閉じて印を残す
        print(f"::warning::{what} は期限の足が7日たっても無い。気配で閉じた")
        return actual, "ticker"
    return None, "none"


def run_pair(pair: str, *, n: datetime, this_hour: int, preds: list[dict], settled: set[str],
             closed_segments: set[str], positions: dict, snapshot: dict) -> None:
    # --- 1. 相場 ---
    pending_t = [p["target_t"] for p in preds if p["pair"] == pair and p["id"] not in settled]
    pos = positions.get(pair)
    need = pending_t + ([pos["close_t"]] if pos else [])
    since = (min(need) - HOUR_MS) if need else None
    candles = market.candles(pair, "1hour", days=WARMUP_DAYS, since_ms=since)
    by_t = {c["t"]: c for c in candles}
    closed = [c for c in candles if c["t"] < this_hour]
    if not closed:
        raise market.MarketError(f"{pair}: 終わった足が無い")
    base = closed[-1]

    # 気配。**約定の値には使わない。**規則の約定値は足の終値（rule_fill）で、run した時刻に左右されない。
    # ここで取るのは「そのとき実際に板にあった値」で、entry_actual / exit_actual と表示に回す。
    # 取れなければ最後に閉じた足の終値で代える（記録に quote_ok=false が残る）
    try:
        t = market.ticker(pair)
        bid, ask, last, quote_ok = t["buy"], t["sell"], t["last"], True
    except market.MarketError as e:
        print(f"[注意] {pair}: 気配が取れない。終値で代える: {e}")
        t = None
        bid = ask = last = base["c"]
        quote_ok = False

    # --- 2. 予測の判定 ---
    for p in preds:
        if p["pair"] != pair or p["id"] in settled:
            continue
        target = by_t.get(p["target_t"])
        if target is None and p["target_t"] + 7 * 24 * HOUR_MS < this_hour:
            # 判定の足が7日たっても無い（取引所が返さない）。判定できないことを記録して閉じる
            append_jsonl(RESULTS, {
                "id": p["id"], "pair": pair, "target_t": p["target_t"], "target_at": p["target_at"],
                "direction": p["direction"], "confidence": p.get("confidence"), "model": p["model"],
                "base_price": p["base_price"], "target_price": None, "move_pct": None,
                "hit": None, "note": "判定の足が無い", "settled_at": iso(n),
            })
            settled.add(p["id"])
            print(f"::warning::{p['id']} は判定の足が7日たっても無い。判定できないまま閉じた")
            continue
        if target is None or p["target_t"] >= this_hour:
            continue
        hit = None
        if p["direction"] != "none":
            move = target["c"] - p["base_price"]
            hit = (move > 0 and p["direction"] == "up") or (move < 0 and p["direction"] == "down")
        append_jsonl(RESULTS, {
            "id": p["id"], "pair": pair, "target_t": p["target_t"],
            "target_at": p["target_at"], "direction": p["direction"],
            "confidence": p.get("confidence"), "model": p["model"],
            "base_price": p["base_price"], "target_price": target["c"],
            "move_pct": round((target["c"] - p["base_price"]) / p["base_price"] * 100, 4),
            "hit": hit, "settled_at": iso(n),
        })
        settled.add(p["id"])
        print(f"[判定] {p['id']} {p['direction']} 的中={hit}")

    # --- 3. 予測 ---
    pid = f"{pair}-{base['t']}"
    target_t = base["t"] + HORIZON_MS
    call = next((p for p in preds if p["id"] == pid), None)
    if call is None:
        call = strategy.decide(closed)
        if call is None:
            print(f"[skip] {pair}: 足が足りない")
        else:
            row = {"id": pid, "pair": pair, "made_at": iso(n),
                   "base_t": base["t"], "base_at": at(base["t"]), "base_close_at": at(base["t"] + HOUR_MS),
                   "base_price": base["c"], "price_at_publish": last, "quote_ok": quote_ok,
                   "target_t": target_t, "target_at": at(target_t), "target_close_at": at(target_t + HOUR_MS),
                   **call}
            append_jsonl(PREDICTIONS, row)
            preds.append(row)
            print(f"[予測] {pid} {call['direction']} {call['reason']}")

    # --- 4. 手仕舞い or 持ち越し ---
    if pos and pos["close_t"] < this_hour:
        seg = int(pos.get("seg", 1))
        # 持ち越すのは、同じモデル・同じ規則で建てた玉だけ。前の版の玉は必ず手仕舞う（台帳を混ぜない）
        same = (bool(call) and call["direction"] == pos["direction"] and pos["direction"] in paper.TRADE_DIRECTIONS
                and pos.get("rule") == paper.RULE and pos.get("model") == call["model"])
        seg_id = f"{pos['id']}-{seg}"
        closes = not same
        # 実際に板にあった値。規則の値との差が「実行のずれ」になる。消さずに横へ残す
        actual = last if same else (bid if pos["direction"] == "up" else ask)
        exit_px, fill_source = rule_fill(by_t, pos["close_t"], actual, this_hour,
                                         old_rule=(pos.get("rule") != paper.RULE), what=seg_id)
        if exit_px is None:
            print(f"::warning::{pair}: 期限 {at(pos['close_t'])} の足がまだ取れない。この回は閉じずに次へ回す")
        else:
            if seg_id not in closed_segments:
                pnl = paper.settle(pair, pos["direction"], pos["entry"], exit_px, pos["open_t"], pos["close_t"],
                                   opens=(seg == 1), closes=closes)
                move = exit_px - pos["entry"]
                # 規則どおりの約定時刻は「期限の足が閉じた瞬間」＝ close_t の1時間後。そこから何分おくれて書いたか
                due = pos["close_t"] + HOUR_MS
                late_min = max(0, int((int(n.timestamp() * 1000) - due) / 60_000))
                append_jsonl(TRADES, {
                    "id": seg_id, "pair": pair, "model": pos["model"], "rule": pos.get("rule", "close-72h-v1"),
                    "direction": pos["direction"], "seg": seg,
                    "open_t": pos["open_t"], "open_at": at(pos["open_t"]),
                    "close_t": pos["close_t"], "close_at": at(pos["close_t"]),
                    "hours": int((pos["close_t"] - pos["open_t"]) / HOUR_MS),
                    "entry": pos["entry"], "exit": exit_px, "opens": seg == 1, "closes": closes,
                    "hit": (move > 0 and pos["direction"] == "up") or (move < 0 and pos["direction"] == "down"),
                    # 規則の値と、実際に板にあった値。両方出す
                    "entry_actual": pos.get("entry_actual"), "exit_actual": actual,
                    "fill_source": fill_source, "late_minutes": late_min,
                    "quote_ok": quote_ok, "filled_t": due, "settled_at": iso(n),
                    **pnl,
                })
                closed_segments.add(seg_id)
                print(f"[{'持ち越し' if same else '手仕舞い'}] {seg_id} 手数料後 {pnl['net_pct']}%")
                if late_min > 60:
                    gap = (actual - exit_px) / exit_px * 100
                    print(f"::warning::{seg_id} を期限から {late_min}分おくれて書いた。"
                          f"規則の値 {exit_px:,.0f} に対し、板は {actual:,.0f}（{gap:+.2f}%）だった")
            if same:
                pos.update({
                    # 持ち越しの境目は、閉じた区間の手仕舞い値と同じ瞬間。同じ値を使う
                    "entry": exit_px, "entry_actual": actual, "seg": seg + 1,
                    "open_t": pos["close_t"], "open_at": at(pos["close_t"]),
                    "close_t": pos["close_t"] + HORIZON_MS, "close_at": at(pos["close_t"] + HORIZON_MS),
                    "carried_at": iso(n),
                })
                positions[pair] = pos
            else:
                positions.pop(pair, None)
                pos = None
            write_json(POSITIONS, positions)

    # --- 5. 建てる ---
    if pos is None and call and call["direction"] in paper.TRADE_DIRECTIONS:
        # 規則の建て値は、合図にした足の終値。run した時刻に左右されない
        entry = base["c"]
        entry_actual = ask if call["direction"] == "up" else bid
        # 足が閉じた瞬間から何分おくれて建てたか。合図は毎時5分なので、ふだんは数分に収まる
        late_min = max(0, int((int(n.timestamp() * 1000) - (base["t"] + HOUR_MS)) / 60_000))
        pos = {
            "id": pid, "pair": pair, "model": call["model"], "rule": paper.RULE,
            "direction": call["direction"], "seg": 1,
            "open_t": base["t"], "open_at": at(base["t"]),
            "close_t": target_t, "close_at": at(target_t),
            "entry": entry, "entry_actual": entry_actual, "entry_late_minutes": late_min,
            "signal_price": base["c"], "opened_at": iso(n), "quote_ok": quote_ok,
        }
        positions[pair] = pos
        write_json(POSITIONS, positions)
        gap = (entry_actual - entry) / entry * 100
        print(f"[建てる] {pair} {call['direction']} @{entry:,.0f}"
              f"（板は {entry_actual:,.0f}／{gap:+.2f}%・{late_min}分後）")
        if late_min > 60:
            print(f"::warning::{pair} を足が閉じてから {late_min}分後に建てた。板との差 {gap:+.2f}%")

    # --- 表示用 ---
    shown = None
    if pos:
        mark = bid if pos["direction"] == "up" else ask
        raw = (mark - pos["entry"]) / pos["entry"]
        if pos["direction"] == "down":
            raw = -raw
        cost = paper.side_cost(pair) * (2 if int(pos.get("seg", 1)) == 1 else 1)
        if pos["direction"] == "down":
            cost += paper.MARGIN_DAILY * jst_midnights(pos["open_t"], int(n.timestamp() * 1000))
        shown = {**pos, "unrealized_pct": round((raw - cost) * 100, 3)}
    snapshot["pairs"][pair] = {
        "ticker": t or {"pair": pair, "last": last, "buy": bid, "sell": ask, "high": None, "low": None,
                        "open": base["c"], "vol": None, "t": base["t"], "fallback": True},
        "position": shown,
        "candles": [{"t": c["t"], "c": c["c"]} for c in closed[-120:]],
    }


def run() -> None:
    n = now()
    this_hour = hour_start_ms(n)
    preds = read_jsonl(PREDICTIONS)
    settled = {r["id"] for r in read_jsonl(RESULTS)}
    closed_segments = {t["id"] for t in read_jsonl(TRADES)}
    positions = {k: v for k, v in (read_json(POSITIONS, {}) or {}).items() if v}
    snapshot = {"generated_at": iso(n), "pairs": {}}
    failed: list[str] = []

    for pair in market.PAIRS:
        try:
            run_pair(pair, n=n, this_hour=this_hour, preds=preds, settled=settled,
                     closed_segments=closed_segments, positions=positions, snapshot=snapshot)
        except market.MarketError as e:
            failed.append(pair)
            print(f"::warning::{pair} の相場が取れなかった。この回は飛ばす: {e}")
        except Exception:
            failed.append(pair)
            import traceback
            traceback.print_exc()
            print(f"::warning::{pair} で想定外の例外。この回は飛ばす（もう1銘柄の記録は残す）")

    write_json(POSITIONS, positions)
    prev = read_json(MARKET, {}) or {}
    # 落ちた銘柄は前回の表示を残す（stale の印を付ける）
    for pair in failed:
        if pair in (prev.get("pairs") or {}):
            snapshot["pairs"][pair] = {**prev["pairs"][pair], "stale": True}
    write_json(MARKET, snapshot)

    import report
    s = report.build(failed_pairs=failed)
    g = s["gate"]
    gates = " ".join(f"{p}:{v['trades']}/{v['next_checkpoint']} t={v['t']}" for p, v in g["per_pair"].items())
    print(f"[集計] 予測 {s['made']}件／判定 {s['predictions']['all']['judged']}件"
          f"／的中率 {s['predictions']['all']['hit_rate']}"
          f"／売買 {g['trades']}件／平均 {g['avg_net_pct']}%／関門 {gates or '未'}")
    if failed:
        print(f"::warning::落ちた銘柄: {failed}")


if __name__ == "__main__":
    run()
