"""予測のやり方。

いまの版は ema-cross-v1 と呼ぶ。短い平均が長い平均より上なら上、下なら下と読む。
差が小さいときは見送る。当てにいかないことも記録に残す。

**判定は72時間後。**1時間や4時間では、当てても手数料に届かない。
90日ぶんの実測で、1時間の平均の値幅は0.25%しかなく、往復の手数料0.34%を下回る。
100%当てても負ける。だから3日を単位にした。根拠は /method/ に出す。

⚠ パラメータは、結果を見る前に決めた値のまま動かしていない。
   後から成績のいい値へ寄せると、その時点で成績は過去への当てはめになる。
⚠ モデルを変えたら MODEL の名前を必ず変える。名前を変えないと違うやり方の成績が同じ欄に混ざる。
"""
from __future__ import annotations

MODEL = "ema-cross-v1"
FAST, SLOW, ATR_N = 12, 48, 24
HORIZON_HOURS = 72
QUIET = 0.15


def ema(values: list[float], n: int) -> float:
    k = 2 / (n + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e


def atr_pct(candles: list[dict], n: int = ATR_N) -> float:
    """値動きの幅を、終値に対する割合で返す。"""
    rows = candles[-(n + 1):]
    if len(rows) < 2:
        return 0.0
    trs = []
    for prev, cur in zip(rows, rows[1:]):
        tr = max(cur["h"] - cur["l"], abs(cur["h"] - prev["c"]), abs(prev["c"] - cur["l"]))
        trs.append(tr / cur["c"])
    return sum(trs) / len(trs)


def decide(candles: list[dict]) -> dict | None:
    """足の並びから、次の72時間の方向を決める。足が足りなければ None を返す。"""
    if len(candles) < SLOW + 2:
        return None
    closes = [c["c"] for c in candles]
    fast = ema(closes[-FAST * 3:], FAST)
    slow = ema(closes[-SLOW * 3:], SLOW)
    width = atr_pct(candles)
    spread = (fast - slow) / slow if slow else 0.0

    if width <= 0 or abs(spread) < QUIET * width:
        direction, confidence = "none", 0.0
    else:
        direction = "up" if spread > 0 else "down"
        strength = min(abs(spread) / width, 2.0)
        confidence = round(0.50 + 0.175 * strength, 4)

    return {
        "model": MODEL,
        "horizon_hours": HORIZON_HOURS,
        "direction": direction,
        "confidence": confidence,
        "reason": {
            "ema_fast": round(fast, 2),
            "ema_slow": round(slow, 2),
            "spread_pct": round(spread * 100, 4),
            "atr_pct": round(width * 100, 4),
            "quiet_line_pct": round(QUIET * width * 100, 4),
        },
    }
