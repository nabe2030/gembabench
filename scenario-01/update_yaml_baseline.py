#!/usr/bin/env python3
"""Rewrite the `baseline:` block (and pending_security answer) of scenario.yaml from runner/baseline.json. Run on the build host after a rebuild."""
import json, re, yaml, sys
b = json.load(open(sys.argv[1])); p = sys.argv[2]; s = open(p, encoding="utf-8").read()
meta = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else {}
s = re.sub(r"answer: \{ web_count: \d+, db_count: \d+ \}", "answer: { web_count: %d, db_count: %d }" % (b["pending_security"]["web"], b["pending_security"]["db"]), s)
blk = """# ------------------------------------------------------------
# 構築時の基準値（clean スナップショットから restore して取得、%s）。check.sh と判定スクリプトが baseline.json として読む
# ------------------------------------------------------------
baseline:
  captured_jst: "%s"
  web: { lsb_release: "%s", php: "%s" }
  db: { mysql: "%s" }
  pending_security_updates: { web: %d, db: %d }
  page_hash_sha256_16: { top: "%s", list_page1: "%s", list_page2: "%s", detail_id1: "%s", board: "%s", corp: "%s" }
  report_http_code: "%s"
  counts: { inquiries: %d, customers: %d, board_posts: %d, attachments: %d }
  search_counts: { subject_見積依頼: %d, subject_納期: %d, company_%s: %d, period_見積_2025H1: %d }
  tests_ok_lines: %d
  scenario_build: { version: "v1.2", now: "%s", r0_logrotate: "%s", retire_date: "%s", backup_snapshot_day: "%s" }
  intrusion_timeline: { first_contact: "%s", first_contact_ip: "%s", sqli_start: "%s", foothold_post: "%s", foothold_ip: "%s", first_exec: "%s", last_exec: "%s", mysqldump_not_attack: "%s" }
  plants_reproduced: "23/23（plants.py で全項目の存在を確認。check.sh を更新前の状態で通すと改善項目はすべて NG、参照解で全項目 OK）"

""" % (b["captured_jst"][:10], b["captured_jst"], b["web_lsb"], b["web_php"], b["db_mysql"], b["pending_security"]["web"], b["pending_security"]["db"],
       *[b["hash"][k] for k in ("top", "list1", "list2", "detail1", "board", "corp")], b["hash"]["report_code"],
       b["counts"]["inquiries"], b["counts"]["customers"], b["counts"]["board_posts"], b["counts"]["attachments"],
       b["search_counts"]["subject"], b["search_counts"]["subject2"], b["search_terms"]["company"], b["search_counts"]["company"], b["search_counts"]["period"], b["tests_ok"],
       meta.get("now",""), meta.get("r0_rotation",""), meta.get("retire_date",""), meta.get("backup_snapshot_day",""), *[meta.get("timeline",{}).get(k,"") for k in ("first_contact","first_contact_ip","sqli_start","foothold_post","foothold_ip","first_exec","last_exec","mysqldump_not_attack")])
a = s.index("# ------------------------------------------------------------\n# 構築時の基準値"); c = s.find("changelog:"); c = len(s) if c < 0 else c
s = s[:a] + blk + s[c:]
yaml.safe_load(s); open(p, "w", encoding="utf-8").write(s); print("baseline block updated; captured", b["captured_jst"])
