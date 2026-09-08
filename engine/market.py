"""bitbank の公開APIから価格を取る。鍵は要らない。

1時間足は日付（YYYYMMDD）で1日ぶんずつ返ってくる。日足は年（YYYY）で1年ぶん返ってくる。
返り値の ohlcv は [始値, 高値, 安値, 終値, 出来高, 時刻ms] の並びで、すべて文字列で来る。

⚠ **この日付は UTC 基準。JSTで組み立てると 00:00〜09:00 JST の9時間ずっと404になる。**
   実測（2026-09-09 06:38 JST）：UTCの 20260908 が「09-08 09:00 〜 09-09 06:00 JST」の22本を持ち、
   JSTの 20260909 は404。2026-09-08にJSTで組み立てて、定時実行を2回落とした。
⚠ **まだ足の無い日は404を返す。**これは異常ではないので、その日だけ飛ばす。
   他のHTTPエラーは今までどおり失敗として上げる（区別を潰さない）。
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import requests

BASE = "https://public.bitbank.cc"
PAIRS = ["btc_jpy", "eth_jpy"]
UA = {"User-Agent": "quant-live/0.1 (+https://ann1678.com/)"}


class MarketError(RuntimeError):
    pass


class NoData(MarketError):
    """その日の足がまだ無い（404）。異常ではない。"""


def _get(url: str) -> dict:
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=20)
            if r.status_code == 404:
                raise NoData(url)
            r.raise_for_status()
            body = r.json()
        except NoData:
            raise
        except Exception as e:
            if attempt == 2:
                raise MarketError(f"{url} を取れなかった: {e}") from e
            time.sleep(2 * (attempt + 1))
            continue
        if body.get("success") != 1:
            raise MarketError(f"{url} がエラーを返した: {body}")
        return body["data"]
    raise MarketError(url)


def candles(pair: str, span: str = "1hour", days: int = 7) -> list[dict]:
    """直近 days 日ぶんの足を、古い順で返す。日付は **UTC** で組み立てる。"""
    out: list[dict] = []
    today = datetime.now(timezone.utc).date()
    for back in range(days - 1, -1, -1):
        d = today - timedelta(days=back)
        try:
            data = _get(f"{BASE}/{pair}/candlestick/{span}/{d.strftime('%Y%m%d')}")
        except NoData:
            continue          # その日はまだ足が無い。飛ばす
        for c in data["candlestick"]:
            if c["type"] != span:
                continue
            for o, h, l, cl, v, ts in c["ohlcv"]:
                out.append({
                    "t": int(ts),
                    "o": float(o), "h": float(h), "l": float(l), "c": float(cl),
                    "v": float(v),
                })
    out.sort(key=lambda x: x["t"])
    # 同じ時刻が二重に入ることがあるので落とす
    seen, uniq = set(), []
    for c in out:
        if c["t"] in seen:
            continue
        seen.add(c["t"])
        uniq.append(c)
    return uniq


def candles_year(pair: str, year: int, span: str = "1day") -> list[dict]:
    data = _get(f"{BASE}/{pair}/candlestick/{span}/{year}")
    out = []
    for c in data["candlestick"]:
        if c["type"] != span:
            continue
        for o, h, l, cl, v, ts in c["ohlcv"]:
            out.append({"t": int(ts), "o": float(o), "h": float(h), "l": float(l),
                        "c": float(cl), "v": float(v)})
    out.sort(key=lambda x: x["t"])
    return out


def ticker(pair: str) -> dict:
    d = _get(f"{BASE}/{pair}/ticker")
    return {
        "pair": pair,
        "last": float(d["last"]),
        "buy": float(d["buy"]),
        "sell": float(d["sell"]),
        "high": float(d["high"]),
        "low": float(d["low"]),
        "open": float(d["open"]),
        "vol": float(d["vol"]),
        "t": int(d["timestamp"]),
    }
