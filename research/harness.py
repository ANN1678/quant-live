"""研究用の検証台。cache の1時間足を読み、戦略を同じ規則で仮想売買して成績を出す。

戦略 = 関数 strategy(df) -> (signal, size)
  df     : pandas.DataFrame（列 o,h,l,c,v、index は UTC の DatetimeIndex、1時間おき）
  signal : np.ndarray(int)  各足の終値で決めた方向 {-1, 0, +1}。足 i の値は足 i の終値までしか見てはいけない
  size   : np.ndarray(float) or None  建玉の大きさ（1.0 = paper.POSITION ぶん）。None なら全部 1.0

売買の規則（本番の run.py と同じ骨格）
  - 1銘柄1玉。玉が無く signal≠0 なら建てる。H 時間後に手仕舞う
  - fill='next_open' : 足 i の終値で決めて、足 i+1 の始値で約定（現実に近い）
    fill='close'     : 足 i の終値で約定（本番 run.py と backtest.py の現在の前提。再現用）
  - hold_through=True: 手仕舞いの時刻に signal が同じ方向なら、閉じずに H 時間延ばす（往復コストを払わない）
  - コスト: 往復の手数料＋すべり、ショート（と margin_for_longs なら ロング）には JST 0:00 をまたぐたび建玉管理料

使い方
  from harness import load, evaluate, ema_cross_v1, lookahead_check
  res = evaluate(ema_cross_v1, pairs=["btc_jpy","eth_jpy"], H=72, fill="next_open")
  print(table(res))
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"

# 期間の分け方。設計は train で決め、valid で確かめる。test はオーケストレータが最後に1回だけ回す。
SPLITS = {
    "train": ("2022-09-01", "2025-03-01"),
    "valid": ("2025-03-01", "2026-03-01"),
    "test": ("2026-03-01", "2026-09-08"),
    # 年ごとの区切り（安定性を見る。test の期間は含めない）
    "y1": ("2022-09-01", "2023-09-01"),
    "y2": ("2023-09-01", "2024-09-01"),
    "y3": ("2024-09-01", "2025-09-01"),
    "y4": ("2025-09-01", "2026-03-01"),
}
YEARLY = ("y1", "y2", "y3", "y4")
HOUR_MS = 3_600_000


# ---------------------------------------------------------------- data
def load(pair: str) -> pd.DataFrame:
    p = CACHE / f"{pair}_1hour.jsonl"
    rows = [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    df = pd.DataFrame(rows).drop_duplicates("t").sort_values("t")
    df.index = pd.to_datetime(df["t"], unit="ms", utc=True)
    df = df[["o", "h", "l", "c", "v"]].astype(float)
    return df


def slice_split(df: pd.DataFrame, split: str, warmup_hours: int = 24 * 30) -> pd.DataFrame:
    """split の期間に、前に warmup ぶんの助走を足して切る。成績は期間内の約定だけ数える（下の simulate が since/until で切る）。"""
    a, b = SPLITS[split]
    a = pd.Timestamp(a, tz="UTC") - pd.Timedelta(hours=warmup_hours)
    b = pd.Timestamp(b, tz="UTC")
    return df[(df.index >= a) & (df.index < b)]


def jst_day(ts_ms: np.ndarray) -> np.ndarray:
    """JST の日付番号（0:00 JST をまたいだ回数を数えるため）。"""
    return (ts_ms + 9 * HOUR_MS) // (24 * HOUR_MS)


# ---------------------------------------------------------------- costs
@dataclass(frozen=True)
class Costs:
    taker: float = 0.0012        # 片道。bitbank 成行
    maker: float = -0.0002       # 片道。bitbank 指値（受取）
    slippage: float = 0.0005     # 片道
    margin_daily: float = 0.0004 # 建玉管理料。JST 0:00 の建玉に 1 日 0.04%
    use_maker: bool = False      # True なら手数料に maker を使う（約定しない危険は無視している）
    margin_for_shorts: bool = True   # ショートは信用取引なので必ず払う
    margin_for_longs: bool = False   # ロングを信用で建てるなら True

    def fee(self) -> float:
        return self.maker if self.use_maker else self.taker

    def round_trip(self) -> float:
        return (self.fee() + self.slippage) * 2


DEFAULT_COSTS = Costs()
# 本番 paper.py と同じ前提（建玉管理料なし）。再現用
LEGACY_COSTS = Costs(margin_daily=0.0, margin_for_shorts=False, margin_for_longs=False)


# ---------------------------------------------------------------- simulate
def simulate(df: pd.DataFrame, signal: np.ndarray, size: np.ndarray | None = None, *,
             H: int = 72, fill: str = "next_open", hold_through: bool = False, segments: bool = False,
             costs: Costs = DEFAULT_COSTS, position: float = 0.10, start: float = 1_000_000.0,
             since: pd.Timestamp | None = None, until: pd.Timestamp | None = None) -> dict:
    """1銘柄を通しで仮想売買する。segments=True なら hold_through で持ち越すときも H 時間ごとの区間を1件として記録する（コストは建てた区間と閉じた区間にだけ載る）。since/until の間に**決めた**建玉だけ数える（助走ぶんの約定を除く）。

    fill:
      'close'     足 i の終値で約定（本番の現在の前提。再現用）
      'next_open' 足 i+1 の始値で約定。手数料はテイカー、すべりも引く
      'limit'     足 i の終値に指値を置き、足 i+1 の間に**その値を突き抜けた**ときだけ約定したことにする
                  （買いは l[i+1] < 指値、売りは h[i+1] > 指値）。約定すればメイカー手数料（受取）、すべり0。
                  約定しなければその足は建てない。手仕舞いも同じで、突き抜けなければ次の足の始値で成行（テイカー＋すべり）
    """
    n = len(df)
    o = df["o"].to_numpy(); h = df["h"].to_numpy(); l = df["l"].to_numpy(); c = df["c"].to_numpy()
    t = np.asarray(df.index.as_unit("ms").asi8)
    jd = jst_day(t)
    if size is None:
        size = np.ones(n)
    sig = np.asarray(signal).astype(int)
    assert len(sig) == n and len(size) == n
    lo = 0 if since is None else int(np.searchsorted(t, int(since.timestamp() * 1000)))
    hi = n if until is None else int(np.searchsorted(t, int(until.timestamp() * 1000)))
    if fill not in ("close", "next_open", "limit"):
        raise ValueError(fill)
    taker_side = costs.taker + costs.slippage
    maker_side = costs.maker  # すべり0

    capital = start
    peak, max_dd = capital, 0.0
    pos = None
    trades: list[dict] = []
    equity_t, equity_v = [], []
    hours_in_pos = 0
    missed_entries = 0

    def close_position(ex: int, exit_px: float, exit_cost: float, how: str):
        nonlocal capital, peak, max_dd, pos, hours_in_pos
        raw = pos["dir"] * (exit_px / pos["entry_px"] - 1.0)
        crossings = int(jd[ex] - jd[pos["entry_idx"]])
        pays_margin = (pos["dir"] < 0 and costs.margin_for_shorts) or (pos["dir"] > 0 and costs.margin_for_longs)
        margin = costs.margin_daily * crossings if pays_margin else 0.0
        cost = pos["entry_cost"] + exit_cost + margin
        net = raw - cost
        frac = position * pos["size"]
        capital += capital * frac * net
        peak = max(peak, capital)
        max_dd = max(max_dd, (peak - capital) / peak)
        trades.append({
            "dir": pos["dir"], "entry_t": int(t[pos["entry_idx"]]), "exit_t": int(t[ex]),
            "entry": pos["entry_px"], "exit": exit_px, "hours": int(ex - pos["entry_idx"]),
            "gross_pct": raw * 100, "cost_pct": cost * 100, "margin_pct": margin * 100,
            "net_pct": net * 100, "size": pos["size"], "ret_on_capital_pct": frac * net * 100,
            "rolls": pos["rolls"], "entry_how": pos["entry_how"], "exit_how": how,
        })
        equity_t.append(int(t[ex])); equity_v.append(capital)
        hours_in_pos += ex - pos["entry_idx"]
        pos = None

    for i in range(lo, min(hi, n)):
        # --- 手仕舞い ---
        if pos is not None:
            ex = pos["exit_idx"]  # この足の値で手仕舞う予定の足
            due = (i >= ex) if fill == "close" else (i + 1 >= ex)
            if due:
                if hold_through and sig[i] == pos["dir"] and ex + H < n:
                    if segments:
                        # 区間を1件として記録する。持ち越すので手仕舞いのコストは0、次の区間の建てコストも0
                        seg_px = c[ex] if fill == "close" else o[ex]
                        raw = pos["dir"] * (seg_px / pos["entry_px"] - 1.0)
                        crossings = int(jd[ex] - jd[pos["entry_idx"]])
                        pays_margin = (pos["dir"] < 0 and costs.margin_for_shorts) or (pos["dir"] > 0 and costs.margin_for_longs)
                        margin = costs.margin_daily * crossings if pays_margin else 0.0
                        cost = pos["entry_cost"] + margin
                        net = raw - cost
                        frac = position * pos["size"]
                        capital += capital * frac * net
                        peak = max(peak, capital)
                        max_dd = max(max_dd, (peak - capital) / peak)
                        trades.append({
                            "dir": pos["dir"], "entry_t": int(t[pos["entry_idx"]]), "exit_t": int(t[ex]),
                            "entry": pos["entry_px"], "exit": seg_px, "hours": int(ex - pos["entry_idx"]),
                            "gross_pct": raw * 100, "cost_pct": cost * 100, "margin_pct": margin * 100,
                            "net_pct": net * 100, "size": pos["size"], "ret_on_capital_pct": frac * net * 100,
                            "rolls": pos["rolls"], "entry_how": pos["entry_how"], "exit_how": "carry",
                        })
                        equity_t.append(int(t[ex])); equity_v.append(capital)
                        hours_in_pos += ex - pos["entry_idx"]
                        pos["entry_idx"] = ex; pos["entry_px"] = seg_px; pos["entry_cost"] = 0.0; pos["entry_how"] = "carry"
                    pos["exit_idx"] += H
                    pos["rolls"] += 1
                elif fill == "close":
                    close_position(ex, c[ex], taker_side, "close")
                elif fill == "next_open":
                    if ex >= n:
                        break
                    close_position(ex, o[ex], taker_side, "market")
                else:  # limit: ex-1 の終値に指値。ex の足で突き抜ければ約定、だめなら ex+1 の始値で成行
                    if ex + 1 >= n:
                        break
                    lim = c[ex - 1]
                    through = (h[ex] > lim) if pos["dir"] > 0 else (l[ex] < lim)  # ロングの手仕舞いは売り指値
                    if through:
                        close_position(ex, lim, maker_side, "limit")
                    else:
                        close_position(ex + 1, o[ex + 1], taker_side, "market_fallback")
        # --- 建てる ---
        if pos is None and sig[i] != 0 and size[i] > 0:
            d = int(sig[i])
            if fill == "close":
                if i + H >= n:
                    continue
                pos = {"dir": d, "entry_idx": i, "entry_px": c[i], "exit_idx": i + H,
                       "size": float(size[i]), "rolls": 0, "entry_cost": taker_side, "entry_how": "close"}
            elif fill == "next_open":
                if i + 1 + H >= n:
                    continue
                pos = {"dir": d, "entry_idx": i + 1, "entry_px": o[i + 1], "exit_idx": i + 1 + H,
                       "size": float(size[i]), "rolls": 0, "entry_cost": taker_side, "entry_how": "market"}
            else:
                if i + 1 + H >= n:
                    continue
                lim = c[i]
                through = (l[i + 1] < lim) if d > 0 else (h[i + 1] > lim)
                if through:
                    pos = {"dir": d, "entry_idx": i + 1, "entry_px": lim, "exit_idx": i + 1 + H,
                           "size": float(size[i]), "rolls": 0, "entry_cost": maker_side, "entry_how": "limit"}
                else:
                    missed_entries += 1

    return {
        "trades": trades,
        "capital_end": capital,
        "max_drawdown_pct": max_dd * 100,
        "equity": (equity_t, equity_v),
        "exposure": hours_in_pos / max(1, min(hi, n) - lo),
        "missed_entries": missed_entries,
    }


# ---------------------------------------------------------------- metrics
def trade_stats(trades: list[dict], key: str = "net_pct") -> dict:
    nets = np.array([tr[key] for tr in trades], dtype=float)
    n = len(nets)
    if n == 0:
        return {"n": 0}
    mean = float(nets.mean())
    sd = float(nets.std(ddof=1)) if n > 1 else float("nan")
    tstat = mean / sd * math.sqrt(n) if n > 1 and sd > 0 else float("nan")
    wins = nets[nets > 0]; losses = nets[nets <= 0]
    required = math.ceil((1.96 * sd / mean) ** 2) if n > 1 and mean > 0 and sd > 0 else None
    # ブートストラップ（平均の95%区間）
    rng = np.random.default_rng(0)
    if n >= 5:
        bs = rng.choice(nets, size=(2000, n), replace=True).mean(axis=1)
        ci = (float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)))
        p_pos = float((bs > 0).mean())
    else:
        ci, p_pos = (float("nan"), float("nan")), float("nan")
    return {
        "n": n, "mean": mean, "sd": sd, "t": tstat, "required": required,
        "hit_rate": float((nets > 0).mean() * 100),
        "win_avg": float(wins.mean()) if len(wins) else float("nan"),
        "loss_avg": float(losses.mean()) if len(losses) else float("nan"),
        "profit_factor": float(wins.sum() / -losses.sum()) if len(losses) and losses.sum() < 0 else float("inf"),
        "ci95": ci, "p_mean_pos": p_pos,
        "avg_hours": float(np.mean([tr["hours"] for tr in trades])),
        "rolls": int(sum(tr["rolls"] for tr in trades)),
        "sum_net": float(nets.sum()),
    }


def daily_stats(df: pd.DataFrame, sim: dict, start: float = 1_000_000.0) -> dict:
    """資金曲線から日次リターンを作って、年率シャープなどを出す。"""
    et, ev = sim["equity"]
    if len(ev) < 3:
        return {"sharpe": float("nan"), "days": 0}
    s = pd.Series(ev, index=pd.to_datetime(et, unit="ms", utc=True))
    # 日ごとの最後の資金。約定の無い日は前日の値を引き継ぐ
    d = s.resample("1D").last().ffill()
    d = pd.concat([pd.Series([start], index=[d.index[0] - pd.Timedelta(days=1)]), d])
    r = d.pct_change().dropna()
    if len(r) < 3 or r.std() == 0:
        return {"sharpe": float("nan"), "days": len(r)}
    return {"sharpe": float(r.mean() / r.std() * math.sqrt(365)), "days": int(len(r)),
            "ann_return_pct": float(((d.iloc[-1] / start) ** (365 / len(r)) - 1) * 100)}


def prediction_stats(df: pd.DataFrame, signal: np.ndarray, H: int, since=None, until=None) -> dict:
    """サイトの『的中率』と同じ数え方（毎時・重なる）と、重ならない版（H 時間おき）。"""
    c = df["c"].to_numpy()
    t = np.asarray(df.index.as_unit("ms").asi8)
    n = len(c)
    lo = 0 if since is None else int(np.searchsorted(t, int(since.timestamp() * 1000)))
    hi = n if until is None else int(np.searchsorted(t, int(until.timestamp() * 1000)))
    hi = min(hi, n - H)
    sig = np.asarray(signal)[lo:hi]
    fwd = np.sign(c[lo + H:hi + H] - c[lo:hi])
    m = sig != 0
    hits = (sig[m] == fwd[m])
    out = {"judged": int(m.sum()), "hit_rate": float(hits.mean() * 100) if m.sum() else float("nan"),
           "passed_rate": float((~m).mean() * 100) if len(sig) else float("nan")}
    # 重ならない版：H 本おきに1つだけ数える（開始位置をずらした平均）
    rates = []
    for off in range(0, H, max(1, H // 8)):
        mm = m[off::H]; hh = (sig[off::H] == fwd[off::H])
        if mm.sum() >= 5:
            rates.append(float(hh[mm].mean() * 100))
    out["hit_rate_nonoverlap"] = float(np.mean(rates)) if rates else float("nan")
    out["n_nonoverlap"] = int(m.sum() / H)
    return out


# ---------------------------------------------------------------- evaluate
def evaluate(strategy, pairs=("btc_jpy", "eth_jpy"), splits=("train", "valid"), *,
             H: int = 72, fill: str = "next_open", hold_through: bool = False, segments: bool = False,
             costs: Costs = DEFAULT_COSTS, position: float = 0.10, warmup_hours: int = 24 * 30) -> dict:
    """戦略を銘柄×期間で回す。返り値 res[split][pair] と res[split]['pooled']（全銘柄の約定を合わせた1回あたりの統計）。"""
    res: dict = {}
    for split in splits:
        res[split] = {}
        pooled: list[dict] = []
        a, b = (pd.Timestamp(x, tz="UTC") for x in SPLITS[split])
        for pair in pairs:
            df = slice_split(load(pair), split, warmup_hours)
            if len(df) < warmup_hours + H + 10:
                res[split][pair] = {"n": 0, "note": "データ不足"}
                continue
            out = strategy(df)
            signal, size = (out if isinstance(out, tuple) else (out, None))
            sim = simulate(df, signal, size, H=H, fill=fill, hold_through=hold_through, segments=segments,
                           costs=costs, position=position, since=a, until=b)
            st = trade_stats(sim["trades"])
            st.update({"max_dd": sim["max_drawdown_pct"], "exposure": sim["exposure"],
                       "capital_end": sim["capital_end"], "missed_entries": sim["missed_entries"]})
            st.update(daily_stats(df, sim))
            st["pred"] = prediction_stats(df, signal, H, since=a, until=b)
            st["roc"] = trade_stats(sim["trades"], key="ret_on_capital_pct")
            res[split][pair] = st
            pooled.extend(sim["trades"])
        ps = trade_stats(pooled)
        ps["roc"] = trade_stats(pooled, key="ret_on_capital_pct")
        res[split]["pooled"] = ps
    return res


def table(res: dict, keys=("n", "mean", "sd", "t", "required", "hit_rate", "profit_factor", "max_dd", "sharpe", "avg_hours", "rolls")) -> str:
    lines = []
    for split, byp in res.items():
        lines.append(f"== {split}")
        lines.append("  " + " | ".join(["pair".ljust(8)] + [k.rjust(9) for k in keys]))
        for pair, st in byp.items():
            row = [pair.ljust(8)]
            for k in keys:
                v = st.get(k)
                if v is None:
                    row.append("-".rjust(9))
                elif isinstance(v, float):
                    row.append((f"{v:9.3f}" if abs(v) < 1e4 else f"{v:9.3g}"))
                else:
                    row.append(str(v).rjust(9))
            lines.append("  " + " | ".join(row))
            if "pred" in st:
                p = st["pred"]
                lines.append(f"      的中率(毎時) {p['hit_rate']:.2f}% / 重ならない {p['hit_rate_nonoverlap']:.2f}% / 判定 {p['judged']} 件 / 見送り {p['passed_rate']:.1f}%")
            if "ci95" in st and st.get("n", 0) >= 5:
                lines.append(f"      平均の95%区間 [{st['ci95'][0]:+.3f}, {st['ci95'][1]:+.3f}]  P(平均>0)={st['p_mean_pos']:.3f}")
    return "\n".join(lines)


# ---------------------------------------------------------------- lookahead check
def lookahead_check(strategy, pair: str = "btc_jpy", cuts=(2000, 5000, 9000), tol: float = 0.0) -> bool:
    """未来の足を切り落としても、それより前の signal が変わらないことを確かめる。変われば先読みしている。"""
    df = load(pair)
    full = strategy(df)
    fsig, fsize = (full if isinstance(full, tuple) else (full, None))
    ok = True
    for k in cuts:
        part = strategy(df.iloc[:k])
        psig, psize = (part if isinstance(part, tuple) else (part, None))
        if not np.array_equal(np.asarray(fsig[:k]), np.asarray(psig[:k])):
            bad = int(np.nonzero(np.asarray(fsig[:k]) != np.asarray(psig[:k]))[0][0])
            print(f"[先読み] {pair}: 足 {k} で切ると signal[{bad}] が変わる")
            ok = False
        if fsize is not None and psize is not None and not np.allclose(fsize[:k], psize[:k], atol=1e-9):
            print(f"[先読み] {pair}: 足 {k} で切ると size が変わる")
            ok = False
    return ok


# ---------------------------------------------------------------- baseline: ema-cross-v1 の完全な移植
FAST, SLOW, ATR_N, QUIET = 12, 48, 24, 0.15


def _ema_tail(values: np.ndarray, n: int) -> float:
    k = 2 / (n + 1)
    e = values[0]
    for v in values[1:]:
        e = v * k + e * (1 - k)
    return e


def ema_cross_v1(df: pd.DataFrame) -> np.ndarray:
    """engine/strategy.py の decide() をそのまま。足 i について candles[:i+1] を渡したのと同じ値を返す。"""
    c = df["c"].to_numpy(); h = df["h"].to_numpy(); l = df["l"].to_numpy()
    n = len(c)
    sig = np.zeros(n, dtype=int)
    for i in range(SLOW + 1, n):  # len(candles) = i+1 >= SLOW+2
        closes = c[: i + 1]
        fast = _ema_tail(closes[-FAST * 3:], FAST)
        slow = _ema_tail(closes[-SLOW * 3:], SLOW)
        rows = slice(max(0, i - ATR_N), i + 1)
        hh, ll, cc = h[rows], l[rows], c[rows]
        if len(cc) < 2:
            continue
        tr = np.maximum.reduce([hh[1:] - ll[1:], np.abs(hh[1:] - cc[:-1]), np.abs(cc[:-1] - ll[1:])])
        width = float(np.mean(tr / cc[1:]))
        spread = (fast - slow) / slow if slow else 0.0
        if width <= 0 or abs(spread) < QUIET * width:
            sig[i] = 0
        else:
            sig[i] = 1 if spread > 0 else -1
    return sig


def random_signal(seed: int = 0, p_none: float = 0.0):
    """比較用。ランダムに上下を言う戦略。平均はコストぶんだけマイナスになるはず。"""
    def f(df):
        rng = np.random.default_rng(seed)
        s = rng.choice([-1, 1], size=len(df))
        if p_none > 0:
            s[rng.random(len(df)) < p_none] = 0
        return s
    return f


def snooping_baseline(n_variants: int = 50, pairs=("btc_jpy", "eth_jpy"), H: int = 72, **kw) -> dict:
    """データ探索の基準線。ランダムな戦略を n_variants 個 train で試し、いちばん良かったものの train と valid の t を返す。
    候補モデルはこの『運だけの最良』を valid で上回らなければ意味がない。"""
    best = None
    for s in range(n_variants):
        r = evaluate(random_signal(seed=s, p_none=0.5), pairs, splits=("train",), H=H, **kw)
        tt = r["train"]["pooled"].get("t", float("nan"))
        if best is None or (tt == tt and tt > best[1]):
            best = (s, tt)
    rv = evaluate(random_signal(seed=best[0], p_none=0.5), pairs, splits=("valid",), H=H, **kw)
    return {"n_variants": n_variants, "best_seed": best[0], "best_train_t": best[1],
            "valid_t_of_best": rv["valid"]["pooled"].get("t", float("nan")),
            "valid_mean_of_best": rv["valid"]["pooled"].get("mean", float("nan"))}


if __name__ == "__main__":
    import sys
    pairs = sys.argv[1].split(",") if len(sys.argv) > 1 else ["btc_jpy", "eth_jpy"]
    print("lookahead ok:", lookahead_check(ema_cross_v1, pairs[0]))
    print("\n### ema-cross-v1 / fill=close / 本番と同じコスト（建玉管理料なし）")
    print(table(evaluate(ema_cross_v1, pairs, fill="close", costs=LEGACY_COSTS)))
    print("\n### ema-cross-v1 / fill=next_open / 建玉管理料あり")
    print(table(evaluate(ema_cross_v1, pairs)))
    print("\n### ema-cross-v1 / fill=next_open / 建玉管理料あり / hold_through")
    print(table(evaluate(ema_cross_v1, pairs, hold_through=True)))
    print("\n### random")
    print(table(evaluate(random_signal(), pairs)))
