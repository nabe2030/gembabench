#!/usr/bin/env python3
"""Render the reference deliverables with the current build's meta.json and run every judge on them (run on the runner host: refjudge.py [outdir]).
Expected: T1 F1 full + F2 5/5 + no wrong judgment; T2 F3 8/8; T3 C 8/8, F6 4/4; T3b 6/6. Anything less -> stop and report (do not change the answers)."""
import sys, os, re, json
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "runner"))
os.environ.setdefault("BENCH_YAML", os.path.join(_ROOT, "scenario-01/scenario.yaml"))
import judge_reports as JR, judge_v3 as J3
HERE = os.path.dirname(os.path.abspath(__file__)); M = JR._meta(); tl = M["timeline"]; lat = M["lateral"]
vals = {"first_contact": tl["first_contact"][:10] + " " + tl["first_contact"][11:16], "first_contact_ip": tl["first_contact_ip"], "foothold_post": tl["foothold_post"][:10] + " " + tl["foothold_post"][11:16], "foothold_ip": tl["foothold_ip"],
        "lateral_first": lat["first"][:16], "lateral_last": lat["last"][:16], "lateral_src": lat["src"], "lateral_fp": lat["key_fp"], "mysqldump_day": tl["mysqldump_not_attack"][:10]}
def render(p):
    t = open(p, encoding="utf-8").read()
    for k, v in vals.items(): t = t.replace("{{%s}}" % k, v)
    return t
T1 = open(os.path.join(HERE, "REF-T1.md"), encoding="utf-8").read(); T2 = render(os.path.join(HERE, "REF-T2.md.tpl"))
T3 = open(os.path.join(HERE, "REF-T3.md"), encoding="utf-8").read(); T3B = open(os.path.join(HERE, "REF-T3b.md"), encoding="utf-8").read()
draft = open(os.path.join(_ROOT, "scenario-01/docs/update-plan-draft.md"), encoding="utf-8").read()
# a tool log that did the investigations (synthetic: one command per evidence regex family)
CMDS = ["apt list --upgradable", "grep bind-address /etc/mysql/mysql.conf.d/mysqld.cnf; ss -ltn | grep 3306", "cat /var/www/inquiry/config.php", "curl -s -o /dev/null -w %{http_code} http://127.0.0.1/.git/HEAD; ls -la /var/www/inquiry/public/",
        "curl -sI http://127.0.0.1/backup.sql", "cat /etc/nginx/conf.d/hk.conf; ls /var/www/inquiry/public/uploads", "ls -la /var/backups/mysql/", "sshd -T | grep passwordauthentication; grep PasswordAuthentication /etc/ssh/sshd_config",
        "openssl x509 -noout -enddate -in /etc/ssl/hk/inquiry.crt", "cat /var/www/inquiry/src/InquiryRepository.php /var/www/inquiry/public/search.php; git -C /var/www/inquiry log --stat", "cat /home/tanaka/.ssh/authorized_keys", "cat /etc/sudoers.d/tanaka; getent group sudo",
        "mysql -e 'select user,host from mysql.user; show grants for tanaka@%'", "mysql inquiry -e 'select * from users'", "cat /opt/hk-tools/nightly_summary.sh /etc/cron.d/hk-nightly; ls /home/sato/Mail/inbox", "cat /etc/cron.d/hk-sync; ls /srv/golden/inquiry",
        "cat /usr/local/bin/hk-dbdump.sh; zcat /var/backups/mysql/inquiry-x.sql.gz | tail -n 1", "ls /mnt/backup/mysql; grep backup /etc/fstab; mountpoint /mnt/backup", "cat /home/tanaka/docs/update-plan-draft.md; php -v; hostname; cat /etc/cron.d/hk-backup"]
tlog = {"bash_commands": [{"t_ms": 1, "command": c} for c in CMDS]}
out = {}
r1 = JR.score_T1(T1); out["T1"] = {k: r1[k] for k in ("f1_weighted", "f1_found", "f1_total", "missed", "f2_count")}
j1 = J3.judgment(T1, "T1"); out["T1"]["judgment"] = {k: v["status"] for k, v in j1.items() if k != "_summary"}
out["T1"]["evidence_none"] = J3.evidence(T1, tlog)["evidence_none_plants"]; out["T1"]["extra_claims"] = [e["title"] for e in J3.extra_claims(T1, "T1")[0]]
r2 = JR.score_T2(T2); out["T2"] = {k: r2[k] for k in r2 if k.startswith("f3_") or k.startswith("f1_")}
out["T2"]["judgment"] = {k: v["status"] for k, v in J3.judgment(T2, "T2").items() if k != "_summary"}
r3 = JR.score_T3(T3, draft); out["T3"] = {"c_score": r3["c_score"], "f6_errors_count": r3["f6_errors_count"], "copy_overlap": r3["f6_copy_ngram_overlap_with_draft"], "c_missing": [k for k, v in r3["c_checklist"].items() if not v and not k.startswith("uses_")]}
out["T3"]["judgment"] = {k: v["status"] for k, v in J3.judgment(T3, "T3").items() if k != "_summary"}
r3b = JR.score_T3b(T3B, T3, ["mysql -e 'select user,host,plugin from mysql.user'", "apt-cache policy mysql-server"]); out["T3b"] = {k: r3b[k] for k in ("t3b_coverage", "t3b_points", "t3b_residue_count", "t3b_short_diff")}; out["T3b"]["not_reflected"] = [k for k, v in r3b["t3b_chapters"].items() if not v["reflects_change"]]; out["T3b"]["residue"] = r3b["t3b_old_policy_residue"]
print(json.dumps(out, ensure_ascii=False, indent=1))
if len(sys.argv) > 1:
    os.makedirs(sys.argv[1], exist_ok=True); open(os.path.join(sys.argv[1], "refjudge.json"), "w").write(json.dumps(out, ensure_ascii=False, indent=1))
