#!/bin/bash
# ビルドしたサイトを ann1678.com のサーバーへ送る。
#
#   scripts/deploy.sh <サーバー側の置き場所>
#   例) scripts/deploy.sh '~/ann1678.com/public_html'
#
# ⚠ rsync と scp は使わない。成功と返ってきても反映されないことがある（2026-08-14の実害）。
#    まとめて1本の tar で送り、md5 で照合してから展開する。
set -euo pipefail

TARGET="${1:-}"
if [ -z "$TARGET" ]; then
  echo "置き場所を渡してください。例) scripts/deploy.sh '~/ann1678.com/public_html'" >&2
  exit 1
fi

KEY="$HOME/.ssh/ann1678.key"
HOST="ann1678@sv17177.xserver.jp"
PORT=10022
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

ssh_do() { ssh -i "$KEY" -p "$PORT" -o BatchMode=yes -o LogLevel=ERROR "$HOST" "$1"; }

echo "[1/5] ビルドする"
cd "$ROOT" && npx astro build >/dev/null

echo "[2/5] 固める"
TMP=$(mktemp -d)
tar czf "$TMP/site.tgz" -C "$ROOT/dist" .
LOCAL_MD5=$(md5 -q "$TMP/site.tgz")

echo "[3/5] 送る"
ssh_do 'mkdir -p ~/deploy'
cat "$TMP/site.tgz" | ssh -i "$KEY" -p "$PORT" -o BatchMode=yes -o LogLevel=ERROR "$HOST" 'cat > ~/deploy/site.tgz'

echo "[4/5] md5 を照合する"
REMOTE_MD5=$(ssh_do 'md5sum ~/deploy/site.tgz' | awk '{print $1}')
if [ "$LOCAL_MD5" != "$REMOTE_MD5" ]; then
  echo "  ✗ 一致しない（手元 $LOCAL_MD5 ／ 向こう $REMOTE_MD5）。展開しないで止める。" >&2
  exit 1
fi
echo "  ✓ $LOCAL_MD5"

echo "[5/5] 展開する → $TARGET"
ssh_do "mkdir -p $TARGET && tar xzf ~/deploy/site.tgz -C $TARGET"
rm -rf "$TMP"
echo "できました。"
