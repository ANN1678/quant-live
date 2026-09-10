"""予測のやり方。

いまの版は tsmom-vote-v2 と呼ぶ。**7日・14日・28日の値動きの向きを多数決する。**
最後に閉じた1時間足の終値を、7日前・14日前・28日前の終値と比べ、上がっていれば1票、下がっていれば−1票。
票の合計がプラスなら「上」、マイナスなら「下」、ちょうど0なら「見送り」。判定は72時間後の終値。

なぜこの形か
- 1時間足の EMA12/48 のクロス（v1）は、4年・6銘柄に当てると的中率 47〜50%、1回あたりの平均損益はマイナスだった。
  90日の +0.22% は、2026-08-18 の1件が作った偶然の窓だった（research/ に全部ある）
- 日次〜週次の時系列モメンタムは文献（Moskowitz-Ooi-Pedersen 2012、Liu-Tsyvinski 2021）に根拠がある。
  7・14・28日はそこから取った値で、成績を見て動かしていない
- とはいえ**優位が証明されたわけではない。**4年の検証で常時ロングをわずかに上回るだけで、t値は 1.0〜1.3。
  だからこれは「事前に登録した仮説」で、関門（report.py）で検査する

⚠ パラメータ（7・14・28・72）は成績を見て寄せていない。寄せた時点で成績は過去への当てはめになる。
⚠ モデルを変えたら MODEL の名前を必ず変える。名前を変えないと違うやり方の成績が同じ欄に混ざる。
⚠ 「自信」は出さない。v1 の confidence は的中率と無関係だった（0.85 の帯で的中 48%）。確率に見える数字を根拠なく出さない。
"""
from __future__ import annotations

MODEL = "tsmom-vote-v2"
LOOKBACK_DAYS = (7, 14, 28)
HORIZON_HOURS = 72
HOUR_MS = 3_600_000
# 28日前の足まで要る。足の欠けに備えて少し余分に持つ
NEED_HOURS = 24 * max(LOOKBACK_DAYS)


def _sign(x: float) -> int:
    return 1 if x > 0 else -1 if x < 0 else 0


def decide(candles: list[dict]) -> dict | None:
    """閉じた足の並び（古い順、最後が基準の足）から、次の72時間の方向を決める。足が足りなければ None。"""
    if not candles:
        return None
    base = candles[-1]
    by_t = {c["t"]: c for c in candles}
    rets: dict[str, float] = {}
    for n in LOOKBACK_DAYS:
        want = base["t"] - n * 24 * HOUR_MS
        # その時刻の足が無ければ、3時間以内の前の足で代える（取引所が返さない時間がまれにある）
        past = next((by_t[want - k * HOUR_MS] for k in range(0, 4) if want - k * HOUR_MS in by_t), None)
        if past is None or past["c"] <= 0:
            continue
        rets[f"r{n}d_pct"] = (base["c"] / past["c"] - 1.0) * 100
    if not rets:
        return None
    votes = sum(_sign(v) for v in rets.values())
    direction = "up" if votes > 0 else "down" if votes < 0 else "none"
    return {
        "model": MODEL,
        "horizon_hours": HORIZON_HOURS,
        "direction": direction,
        "confidence": None,
        "reason": {**{k: round(v, 4) for k, v in rets.items()}, "votes": votes},
    }
