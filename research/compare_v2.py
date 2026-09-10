"""v2 の候補を事前登録する前の最後の比較。train と valid だけ。test は回さない。
比較: (1) 常時ロング  (2) 日次モメンタムの多数決（7/14/28日）ロングのみ  (3) 同・14日だけ
すべて H=72、持ち越し（同方向なら閉じない）、区間会計、成行、DEFAULT_COSTS。"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import numpy as np
from harness import *

def always_long(df):
    return np.ones(len(df), dtype=int)

def tsmom_long(lookbacks=(7, 14, 28)):
    def f(df):
        c = df["c"].to_numpy(); n = len(c)
        votes = np.zeros(n)
        for N in lookbacks:
            k = 24 * N
            r = np.full(n, np.nan)
            r[k:] = c[k:] / c[:-k] - 1.0
            votes += np.where(np.isnan(r), 0, np.sign(r))
        sig = np.where(votes > 0, 1, 0).astype(int)
        # 助走が足りない足は 0
        sig[: 24 * max(lookbacks)] = 0
        return sig
    return f

PAIRS = ["btc_jpy", "eth_jpy"]
if __name__ == "__main__":
    KEYS = ("n", "mean", "sd", "t", "hit_rate", "profit_factor", "max_dd", "sharpe", "avg_hours", "rolls")
    for name, strat in [("always_long", always_long), ("tsmom_long_7_14_28", tsmom_long()), ("tsmom_long_14", tsmom_long((14,)))]:
        print("\n########", name)
        print("lookahead ok:", lookahead_check(strat, "btc_jpy"))
        res = evaluate(strat, PAIRS, splits=("train", "valid"), H=72, hold_through=True, segments=True)
        print(table(res, KEYS))
        ry = evaluate(strat, PAIRS, splits=YEARLY, H=72, hold_through=True, segments=True)
        print("  yearly pooled t:", {k: round(v["pooled"].get("t", float("nan")), 2) for k, v in ry.items()},
              " mean:", {k: round(v["pooled"].get("mean", float("nan")), 3) for k, v in ry.items()})
        r5 = evaluate(strat, ["xrp_jpy", "ltc_jpy", "doge_jpy"], splits=("valid",), H=72, hold_through=True, segments=True)
        print("  other pairs valid:", {p: (v["n"], round(v.get("mean", float("nan")), 3), round(v.get("t", float("nan")), 2)) for p, v in r5["valid"].items() if p != "pooled"})
