#!/bin/bash
# 夜間集計バッチ (作成: tanaka 2025-11)
# 問い合わせ管理システムの集計 API を叩き、総務(sato)の受信箱に結果を置く。
API_TOKEN="@@TANAKA_TOKEN@@"
OUT=/home/sato/Mail/inbox/summary-$(date +%F).txt
RES=$(curl -s -f -H "Host: inquiry.hiiragi-kinzoku.example" -H "Authorization: Bearer ${API_TOKEN}" http://127.0.0.1/api/summary.php) || { echo "nightly_summary: API call failed" >&2; exit 1; }
{
  echo "From: hk-nightly@hk-web01.hiiragi-kinzoku.example"
  echo "To: sato@hiiragi-kinzoku.example"
  echo "Date: $(date '+%a, %d %b %Y %H:%M:%S %z')"
  echo "Subject: [hk-nightly] 問い合わせ日次集計 $(date +%F)"
  echo
  echo "$RES"
} > "$OUT"
chown sato:sato "$OUT"
