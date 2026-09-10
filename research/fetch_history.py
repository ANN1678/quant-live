"""bitbank の1時間足を日ごとに取って、銘柄ごとの JSONL に貯める（研究用のキャッシュ）。
日付は UTC。無い日（上場前など）は 404 が返るので飛ばす。"""
import json, sys, time, datetime as dt
from pathlib import Path
import requests

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache"
UA = {"User-Agent": "quant-live-research/0.1 (+https://ann1678.com/)"}
B = "https://public.bitbank.cc"

def fetch_day(pair, d):
    url = f"{B}/{pair}/candlestick/1hour/{d.strftime('%Y%m%d')}"
    for attempt in range(4):
        try:
            r = requests.get(url, headers=UA, timeout=20)
            if r.status_code == 404:
                return []
            r.raise_for_status()
            j = r.json()
            if j.get("success") != 1:
                return []
            rows = []
            for c in j["data"]["candlestick"]:
                if c["type"] != "1hour":
                    continue
                for o, h, l, cl, v, ts in c["ohlcv"]:
                    rows.append({"t": int(ts), "o": float(o), "h": float(h), "l": float(l), "c": float(cl), "v": float(v)})
            return rows
        except Exception as e:
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{url} failed")

def main(pair, days):
    out = CACHE / f"{pair}_1hour.jsonl"
    have = {}
    if out.exists():
        for line in out.read_text().splitlines():
            if line.strip():
                r = json.loads(line); have[r["t"]] = r
    today = dt.datetime.utcnow().date()
    start = today - dt.timedelta(days=days)
    # 完全に埋まっている日は飛ばす（1日24本）
    d = start
    got = 0
    while d < today:  # 今日（UTC）は形成中なので取らない
        day_start = int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp() * 1000)
        if sum(1 for k in range(24) if (day_start + k * 3600000) in have) == 24:
            d += dt.timedelta(days=1); continue
        rows = fetch_day(pair, d)
        for r in rows:
            have[r["t"]] = r
        got += len(rows)
        d += dt.timedelta(days=1)
        time.sleep(0.05)
    rows = [have[k] for k in sorted(have)]
    out.write_text("".join(json.dumps(r) + "\n" for r in rows))
    print(f"{pair}: {len(rows)} candles, fetched {got} new, "
          f"{dt.datetime.utcfromtimestamp(rows[0]['t']/1000).date() if rows else None} .. "
          f"{dt.datetime.utcfromtimestamp(rows[-1]['t']/1000) if rows else None}")

if __name__ == "__main__":
    pairs = sys.argv[1].split(",")
    days = int(sys.argv[2])
    for p in pairs:
        main(p, days)
