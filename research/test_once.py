"""事前登録した v2 と常時ロングを、取っておいた test 期間で1回だけ測る。"""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
import numpy as np
from harness import *
from compare_v2 import always_long, tsmom_long
KEYS = ("n", "mean", "sd", "t", "hit_rate", "profit_factor", "max_dd", "sharpe")
for name, strat in [("always_long", always_long), ("v2 tsmom_long_7_14_28", tsmom_long())]:
    print("\n########", name, "(TEST 2026-03-01..2026-09-08, once)")
    res = evaluate(strat, ["btc_jpy", "eth_jpy"], splits=("test",), H=72, hold_through=True, segments=True)
    print(table(res, KEYS))
    r5 = evaluate(strat, ["xrp_jpy", "ltc_jpy", "doge_jpy", "sol_jpy"], splits=("test",), H=72, hold_through=True, segments=True)
    print("  other pairs test:", {p: (v.get("n"), round(v.get("mean", float("nan")), 3), round(v.get("t", float("nan")), 2)) for p, v in r5["test"].items() if p != "pooled"})
