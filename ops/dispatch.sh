#!/bin/bash
# 毎時、GitHub に「エンジンを回せ」と合図を出す。Xserver の cron から呼ぶ。
#
# なぜこれが要るか
#   GitHub の予定実行（schedule）は来ない。2026-09-12の実測で 80.3時間に22回、27%だった。
#   分を動かしても変わらない（:05 で28%、:37 で27%）。GitHub 側で後回しにされているので、
#   こちらからは直せない。**外から出した合図（workflow_dispatch）は後回しにされない。**
#   Xserver の cron は5分ごとの site-pull.sh を落とさずに回している。時刻どおりに動く仕組みは、もう持っている。
#
# なぜエンジンごとサーバーへ移さないか
#   いまは GitHub の機械が予測を書いている。**他人の機械が書いた記録**なので、こちらでは細工できない。
#   それが「結果より先に書いた」の証拠になっている。合図だけをこちらが出して、書くのは GitHub のままにする。
#
# 入れ方
#   1. GitHub で fine-grained personal access token を作る
#        Repository access : Only select repositories → ANN1678/quant-live
#        Permissions       : Repository permissions → Actions → Read and write（これだけ）
#      コードは読めない。push もできない。漏れてもエンジンを余計に回されるだけで、記録は二重にならない
#      （予測は pid、手仕舞いは seg_id で弾いている）。
#   2. サーバーに置く
#        mkdir -p ~/.config/quant-live
#        printf '%s' 'github_pat_xxxxx' > ~/.config/quant-live/github-token
#        chmod 700 ~/.config/quant-live && chmod 600 ~/.config/quant-live/github-token
#   3. このファイルを ~/ops/dispatch.sh に置いて chmod +x
#   4. cron に足す（毎時5分。足が閉じた直後に寄せてある）
#        5 * * * * /home/<ユーザー>/ops/dispatch.sh >/dev/null 2>&1
#
# ⚠ トークンには期限がある。切れたら合図が止まり、GitHub の予定実行（1日6回）だけに戻る。
#    止まったことは alive ワークフローの「記録が古くなっていないか」が拾う。
set -u

REPO="ANN1678/quant-live"
WORKFLOW="engine.yml"
REF="main"
TOKEN_FILE="${HOME}/.config/quant-live/github-token"
LOG="${HOME}/dispatch.log"

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "${LOG}"; }

if [ ! -r "${TOKEN_FILE}" ]; then
  log "NG 鍵が無い: ${TOKEN_FILE}"
  exit 1
fi
TOKEN="$(cat "${TOKEN_FILE}")"

# 3回まで試す。GitHub が一時的に落ちていることがある
for i in 1 2 3; do
  code=$(curl -sS -o /tmp/dispatch.out -w '%{http_code}' \
    -X POST \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    --connect-timeout 10 -m 30 \
    "https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches" \
    -d "{\"ref\":\"${REF}\"}" 2>>"${LOG}") || code=000

  # 204 No Content が成功。本文は返らない
  if [ "${code}" = "204" ]; then
    log "OK 合図を出した（${i}回目）"
    exit 0
  fi
  log "NG HTTP ${code}（${i}回目）: $(head -c 300 /tmp/dispatch.out 2>/dev/null)"
  sleep 10
done

log "NG 3回とも合図を出せなかった"
exit 1
