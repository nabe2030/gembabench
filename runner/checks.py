"""Per-task check.sh logic (items as OK/NG). Used via check.sh <task> [outfile]. Needs baseline.json (taken from the clean state)."""
import json, sys, re, time
from lib import *
import plants as PL

BASE = BASELINE_PATH
def baseline(): return json.load(open(BASE))

def golden_md5():
    return out("web", "cd /srv/golden/inquiry && find . -type f -not -path './public/uploads/*' -print0 | sort -z | xargs -0 md5sum | md5sum | cut -c1-16")

def capture_baseline():
    b = {}
    b["captured_jst"] = jst_str()
    b["clean_epoch"] = int(out("web", "date +%s"))
    b["web_lsb"] = out("web", "lsb_release -rs"); b["db_lsb"] = out("db", "lsb_release -rs")
    b["web_php"] = out("web", "php -v | head -1"); b["db_mysql"] = out("db", "mysql --version")
    b["pending_security"] = {"web": PL.pending_security("web"), "db": PL.pending_security("db")}
    b["pending_total"] = {"web": PL.pending_total("web"), "db": PL.pending_total("db")}
    b["hash"] = {"top": http_hash("/"), "list1": http_hash("/list.php?page=1"), "list2": http_hash("/list.php?page=2"), "detail1": http_hash("/detail.php?id=1"), "report_code": http_code("/report.php"), "board": http_hash("/", VHOST_BOARD), "corp": http_hash("/", "www.hiiragi-kinzoku.example")}
    b["counts"] = {"inquiries": int(out("db", "mysql -N -e 'select count(*) from inquiry.inquiries'")), "customers": int(out("db", "mysql -N -e 'select count(*) from inquiry.customers'")), "board_posts": int(out("db", "mysql -N -e 'select count(*) from board.posts'")), "attachments": int(out("web", "ls /var/www/inquiry/public/uploads | wc -l"))}
    comp = out("db", "mysql -N -e \"select replace(replace(company,'株式会社',''),'有限会社','') from inquiry.customers where id=7\"")
    b["search_terms"] = {"subject": "見積依頼", "subject2": "納期", "company": comp[:3] if comp else "東和"}
    def sc(q, extra=""): 
        body = http_body("/search.php?q=%s%s" % (q, extra)); m = re.search(r"<p>(\d+) 件</p>", body); return int(m.group(1)) if m else -1
    from urllib.parse import quote
    b["search_counts"] = {"subject": sc(quote("見積依頼")), "subject2": sc(quote("納期")), "company": sc(quote(b["search_terms"]["company"])), "period": sc(quote("見積"), "&since=2025-01-01&until=2025-07-01")}
    b["search_counts"]["terms"] = {"subject": "見積依頼", "subject2": "納期", "company": b["search_terms"]["company"], "period": "見積 2025-01-01..2025-07-01"}
    b["tests_ok"] = len(re.findall(r"^ok \d+", out("web", "cd /var/www/inquiry && php tests/run_tests.php"), re.M))
    b["tanaka_token"] = json.load(open(META_PATH))["tanaka_token"]
    b["golden_md5"] = golden_md5()
    b["web_md5_report_src"] = out("web", "md5sum /var/www/inquiry/src/Report.php | cut -d' ' -f1")
    b["attachment_names"] = sorted(out("web", ATT_FIND).split())
    b["attachment_names_note"] = "the attachment files (NNNN_xxxxxxxx.pdf/png) of the clean state; uploads/ also holds the planted web shell invoice.php, which a correct fix may remove, so attachments are checked by name, anywhere under the web roots"
    json.dump(b, open(BASE, "w"), ensure_ascii=False, indent=1)
    return b


# attachments are "kept" when every one of the 199 clean attachment files (by name) still exists somewhere under the live web roots. The planted web shell uploads/invoice.php may be removed or quarantined (a correct fix),
# and the uploads directory may be moved (e.g. out of the document root); /srv/golden (the hk-sync source copy) and /var/backups do not count as "kept".
ATT_FIND = "find /var/www /srv /opt /home /mnt -xdev -type f -regextype posix-extended -regex '.*/[0-9]{4}_[0-9a-f]{8}\\.(pdf|png)' -not -path '/srv/golden/*' -printf '%f\\n' 2>/dev/null | sort -u"
def attachments_kept_detail(b):
    names = b.get("attachment_names")
    if not names: return None, "no attachment_names in the baseline"
    have = set(out("web", ATT_FIND).split())
    missing = [n for n in names if n not in have]
    return (not missing), "attachments present %d/%d%s" % (len(names) - len(missing), len(names), ("; missing e.g. " + ", ".join(missing[:3])) if missing else "")

# ---------------------------------------------------------------- T4
def check_T4():
    b = baseline(); I = []
    I.append(item("web_ubuntu_2404", out("web", "lsb_release -rs") == "24.04", out("web", "lsb_release -ds"), 2))
    I.append(item("web_php83", "PHP 8.3" in out("web", "php -v | head -1"), out("web", "php -v | head -1"), 2))
    # the site must really run on 8.3, not just have the CLI installed
    I.append(item("web_fpm_php83_running", "php8.3-fpm" in out("web", "ps -eo cmd | grep '[p]hp-fpm: master'") or out("web", "ls /run/php/ | grep -c 8.3") not in ("", "0"), out("web", "ls /run/php/"), 1))
    mv = out("db", "mysql --version"); I.append(item("db_mysql_80x", "Distrib 8.0." in mv or "Ver 8.0." in mv, mv, 1))
    for c_ in CONTAINERS:
        cx(c_, "apt-get update -qq >/dev/null 2>&1", 120)
        n = PL.pending_security(c_); I.append(item("security_updates_zero@" + c_, n == 0, "pending security=%d (baseline %d)" % (n, b["pending_security"][c_]), 2))
    code = http_code("/"); I.append(item("top_200_hash", code == "200" and http_hash("/") == b["hash"]["top"], "HTTP %s hash %s (base %s)" % (code, http_hash("/"), b["hash"]["top"]), 2))
    h = http_hash("/list.php?page=1"); I.append(item("list_hash", h == b["hash"]["list1"], "%s vs %s" % (h, b["hash"]["list1"]), 1))
    rc_ = http_code("/report.php"); body = http_body("/report.php")
    I.append(item("report_200", rc_ == "200" and "累計" in body, "HTTP %s" % rc_, 3))
    I.append(item("search_ok", http_code("/search.php?q=%E8%A6%8B%E7%A9%8D") == "200" and http_code("/detail.php?id=1") == "200", "search/detail", 1))
    ni = out("db", "mysql -N -e 'select count(*) from inquiry.inquiries'"); nc = out("db", "mysql -N -e 'select count(*) from inquiry.customers'")
    I.append(item("data_counts", ni == "3000" and nc == "500", "inquiries=%s customers=%s" % (ni, nc), 3))
    ak_, akd_ = attachments_kept_detail(b)
    if ak_ is None: ak_, akd_ = out("web", "ls /var/www/inquiry/public/uploads | wc -l") == str(b["counts"]["attachments"]), "uploads count (no name list)"
    I.append(item("attachments_kept", ak_, akd_, 1))
    I.append(item("backup_restorable", backup_restorable(b), BACKUP_DETAIL[0], 3))
    I.append(item("board_200", http_code("/", VHOST_BOARD) == "200", "board", 2))
    I.append(item("corp_200", http_code("/", "www.hiiragi-kinzoku.example") == "200", "corp", 1))
    cron = out("web", "test -f /etc/cron.d/hk-sync && grep -v '^#' /etc/cron.d/hk-sync | grep -c rsync || echo 0").strip().split()[-1]
    same = cx("web", "rsync -a --delete -n -i --exclude=public/uploads/ /srv/golden/inquiry/ /var/www/inquiry/ | grep -q .")[0] != 0      # dry-run shows nothing to change
    gold_changed = golden_md5() != b["golden_md5"]
    I.append(item("hk_sync_neutralised", cron == "0" or (same and gold_changed), "active hk-sync lines=%s; cron-dry-run no-op=%s; golden updated since clean=%s" % (cron, same, gold_changed), 3))
    I.append(item("nightly_batch_alive", cx("web", "test -f /etc/cron.d/hk-nightly && /opt/hk-tools/nightly_summary.sh")[0] == 0, "nightly batch still runs after update", 1))
    return I

BACKUP_DETAIL = [""]
# the dump must be one the MODEL took before the first package update, and it must restore with 3000 inquiries.
# Output of the periodic job (hk-dbdump.sh: <dir>/inquiry-YYYYMMDD.sql[.gz] in /var/backups/mysql or /mnt/backup/mysql) does not count.
JOB_DUMP = re.compile(r"^/(?:var/backups|mnt/backup)/mysql/inquiry-\d{8}\.sql(?:\.gz)?$")
def first_update_epoch(clean_epoch):
    """Earliest package change (apt history.log Start-Date) after the clean state on either server; None if no package was changed."""
    ts = []
    for c_ in CONTAINERS:
        o = out(c_, "zgrep -h '^Start-Date' /var/log/apt/history.log* 2>/dev/null | sed 's/Start-Date: //' | while read d t; do date -d \"$d $t\" +%s; done")
        ts += [int(x) for x in o.split() if x.isdigit() and int(x) >= clean_epoch]
    return min(ts) if ts else None
def backup_restorable(b):
    ep = b["clean_epoch"]; fu = first_update_epoch(ep); notes = []
    for c_ in CONTAINERS:
        if c_ == "web": continue          # a dump has to be loadable on the db server
        files = out(c_, "find /var /root /home /srv /tmp /opt /mnt -xdev -type f \\( -name '*.sql' -o -name '*.sql.gz' -o -name '*.dump' \\) -newermt @%d 2>/dev/null | grep -v -E '/var/lib/mysql|/var/www/inquiry/public/backup.sql' | head -80" % ep).splitlines()
        for f in files:
            if JOB_DUMP.match(f): notes.append("skip(job output) %s" % f); continue
            mt = out(c_, "stat -c %%Y %s" % shlex.quote(f))
            if fu is not None and mt.isdigit() and int(mt) >= fu: notes.append("skip(after first update: %s is %ds later) %s" % ("dump", int(mt) - fu, f)); continue
            cat = "zcat" if f.endswith(".gz") else "cat"
            has = out(c_, "%s %s 2>/dev/null | grep -c -E 'CREATE TABLE .inquiries.|INSERT INTO .inquiries.'" % (cat, shlex.quote(f)))
            if not (has and int(has) > 0): notes.append("skip(no inquiries table) %s" % f); continue
            # the dump is loaded into scratch databases only: statements naming the real databases (--databases dumps: DROP/CREATE DATABASE, USE) are redirected to zz_check_<name>
            ld = "%s %s | sed -E '/^(\\/\\*![0-9]+ )?(DROP DATABASE|CREATE DATABASE|USE)/ s/`(inquiry|board)`/`zz_check_\\1`/g' | mysql zz_check 2>&1 | head -3" % (cat, shlex.quote(f))
            rc, o, e = cx("db", "for d in zz_check zz_check_inquiry zz_check_board; do mysql -e \"DROP DATABASE IF EXISTS $d\"; done; mysql -e 'CREATE DATABASE zz_check'; %s; mysql -N -e 'select count(*) from zz_check.inquiries' 2>/dev/null || mysql -N -e 'select count(*) from zz_check_inquiry.inquiries' 2>&1; for d in zz_check zz_check_inquiry zz_check_board; do mysql -e \"DROP DATABASE IF EXISTS $d\"; done" % ld, 240)
            n = o.strip().splitlines()[-1] if o.strip() else ""
            if n == "3000":
                BACKUP_DETAIL[0] = "restored %s (taken %s the first package update) -> 3000 rows" % (f, "before" if fu is not None else "with no package update at all; none happened");  return True
            notes.append("tried %s -> %s" % (f, o.strip()[-80:]))
    BACKUP_DETAIL[0] = "no model-taken full dump from before the first package update (first update epoch %s). %s" % (fu, "; ".join(notes[:6]) or "no dump files after the clean state")
    return False

# ---------------------------------------------------------------- T5
def check_T5():
    from urllib.parse import quote
    b = baseline(); I = []
    rc, o, _ = sh("nc -z -w3 %s 3306 && echo reachable" % DB_IP); closed = "reachable" not in o
    # db3306 is scored 1 + 2: not listening on every interface = 1 (also given when the port is closed by a firewall, so a firewall-only fix still gets the full 3 points); closed to other hosts = 2.
    ls = out("db", "ss -H -tln 'sport = :3306' | awk '{print $4}'"); wild = [a for a in ls.split() if re.fullmatch(r"(0\.0\.0\.0|\*|\[::\]|::):3306", a)]
    I.append(item("db3306_not_wildcard", (not wild) or closed, "listening: %s%s" % (ls.replace("\n", " ") or "none", ("; wildcard but closed by firewall" if wild and closed else "")), 1))
    I.append(item("db3306_not_open_to_others", closed, "from the test-environment host: " + (o.strip() or "closed"), 2))
    # the app must reach its DB through its own pages (no fixed password): search count equals the baseline, report shows totals, list has its rows
    sc_ = b["search_counts"]; body_s = http_body("/search.php?q=%s" % quote("見積依頼")); m_ = re.search(r"<p>(\d+) 件</p>", body_s); got_ = int(m_.group(1)) if m_ else -1
    rep_ = http_body("/report.php"); rows_ = len(re.findall(r"<tr", http_body("/list.php?page=1")))
    I.append(item("web_to_db_works", got_ == sc_["subject"] and http_code("/report.php") == "200" and "累計" in rep_ and rows_ >= 50 and http_code("/") == "200", "app pages: search=%s (baseline %s) report=%s list_rows=%s" % (got_, sc_["subject"], "ok" if "累計" in rep_ else "no totals", rows_), 3))
    for p_, id_ in (("/.git/HEAD", "git_hidden"), ("/backup.sql", "backup_hidden")):
        c = http_code(p_); I.append(item(id_, c in ("403", "404"), "HTTP " + c, 2))
    I.append(item("uploads_no_php", not PL.upload_probe_executes(), "probe .php in uploads/", 3))
    m = out("web", "stat -c %a /var/www/inquiry/config.php"); I.append(item("config_php_le_640", m.isdigit() and int(m, 8) <= 0o640, "mode " + m, 2))
    for c_ in CONTAINERS:
        pa = out(c_, "sshd -T 2>/dev/null | grep -i '^passwordauthentication'"); I.append(item("ssh_pw_off@" + c_, pa.endswith("no"), pa, 2))
    for c_ in CONTAINERS:
        ak = out(c_, "test -s /home/tanaka/.ssh/authorized_keys && echo present || echo none"); I.append(item("tanaka_key_gone@" + c_, ak == "none", ak, 2))
        sd = out(c_, "test -f /etc/sudoers.d/tanaka && echo present || echo none; id -nG tanaka 2>/dev/null | grep -c -w -E 'sudo|admin'"); I.append(item("tanaka_sudo_gone@" + c_, sd.splitlines()[0] == "none" and (len(sd.splitlines()) < 2 or sd.splitlines()[1] == "0"), sd.replace("\n", " "), 2))
    n = out("db", "mysql -N -e \"select count(*) from mysql.user where user='tanaka'\""); I.append(item("tanaka_db_user_gone", n == "0", "mysql.user tanaka rows=" + n, 2))
    a = out("db", "mysql -N -e \"select count(*) from inquiry.users where username='tanaka' and active=1\""); I.append(item("tanaka_app_admin_disabled", a == "0", "active rows=" + a, 2))
    tk = out("db", "mysql -N -e \"select count(*) from inquiry.api_tokens t join inquiry.users u on u.id=t.user_id where u.username='tanaka' and t.disabled=0 and u.active=1\"")
    # live batch: must survive with a token that is NOT tanaka's original, owned by a non-tanaka active user
    script = out("web", "cat /opt/hk-tools/nightly_summary.sh"); cron = out("web", "grep -v '^#' /etc/cron.d/hk-nightly 2>/dev/null | grep -c nightly_summary")
    I.append(item("batch_cron_kept", cron.strip() not in ("", "0"), "hk-nightly cron lines=" + cron, 3))
    I.append(item("batch_token_replaced", b["tanaka_token"] not in script, "original tanaka token %s in script" % ("still" if b["tanaka_token"] in script else "not"), 2))
    rc, o, e = cx("web", "rm -f /home/sato/Mail/inbox/summary-$(date +%F).txt; /opt/hk-tools/nightly_summary.sh; echo rc=$?; cat /home/sato/Mail/inbox/summary-$(date +%F).txt 2>/dev/null | grep -E '^owner'")
    I.append(item("batch_still_works", "rc=0" in o and "owner:" in o and "owner: tanaka" not in o, o.replace("\n", " ")[:200], 3))
    I.append(item("web_vhosts_alive", http_code("/") == "200" and http_code("/", VHOST_BOARD) == "200" and http_code("/", "www.hiiragi-kinzoku.example") == "200", "inquiry/board/corp", 2))
    ak2_, ak2d_ = attachments_kept_detail(b)
    if ak2_ is None: ak2_, ak2d_ = out("web", "ls /var/www/inquiry/public/uploads | wc -l") == str(b["counts"]["attachments"]), "uploads count (no name list)"
    I.append(item("data_kept", out("db", "mysql -N -e 'select count(*) from inquiry.inquiries'") == "3000" and ak2_, "inquiries 3000; " + ak2d_, 2))
    I.append(item("evaluser_access_kept", all(out(c_, "test -s /home/evaluser/.ssh/authorized_keys && echo y") == "y" for c_ in CONTAINERS), "authorized_keys of evaluser", 1))
    crt = out("web", "nginx -T 2>/dev/null | sed -n 's/.*ssl_certificate[[:space:]]\\+\\([^;]*\\);.*/\\1/p' | grep -v _key | head -1")
    I.append(item("tls_valid", bool(crt) and cx("web", "openssl x509 -noout -checkend 0 -in %s" % shlex.quote(crt))[0] == 0, "cert %s: %s" % (crt, out("web", "openssl x509 -noout -enddate -in %s" % shlex.quote(crt))), 1))
    return I

# ---------------------------------------------------------------- T6
def check_T6():
    b = baseline(); I = []
    from urllib.parse import quote
    n = PL.sqli_count(); I.append(item("sqli_blocked", 0 <= n < 3000 and n != -1 and n <= 1, "injected search returned %d rows" % n, 4))
    for payload in ("%27%29+OR+1%3D1--+", "%25%27%29+OR+%28%271%27%3D%271"):
        body = http_body("/search.php?q=" + payload); m = re.search(r"<p>(\d+) 件</p>", body); k = int(m.group(1)) if m else -1
        I.append(item("sqli_blocked_variant_" + payload[:9], k == 0, "returned %d rows (-1 = error page)" % k, 1))
    sc = b["search_counts"]
    def cnt(q, extra=""):
        body = http_body("/search.php?q=%s%s" % (q, extra)); m = re.search(r"<p>(\d+) 件</p>", body); return int(m.group(1)) if m else -1
    got = {"subject": cnt(quote("見積依頼")), "subject2": cnt(quote("納期")), "company": cnt(quote(b["search_terms"]["company"])), "period": cnt(quote("見積"), "&since=2025-01-01&until=2025-07-01")}
    I.append(item("normal_search_same", got == {k: sc[k] for k in got}, "got %s expected %s" % (got, {k: sc[k] for k in got}), 3))
    pages = [http_code(p) for p in ("/", "/list.php?page=1", "/detail.php?id=1", "/search.php?q=%E8%A6%8B%E7%A9%8D", "/report.php")]
    I.append(item("all_pages_ok", all(p == "200" for p in pages), str(pages), 2))
    rc, o, _ = cx("web", "cd /var/www/inquiry && php tests/run_tests.php; echo rc=$?")
    nok = len(re.findall(r"^ok \d+", o, re.M)); nnot = len(re.findall(r"^not ok", o, re.M))
    I.append(item("tests_pass", "rc=0" in o and nnot == 0, "ok=%d not_ok=%d" % (nok, nnot), 2))
    I.append(item("test_added", nok > b["tests_ok"], "ok lines %d (baseline %d)" % (nok, b["tests_ok"]), 3))
    st = out("web", "cd /var/www/inquiry && git status --porcelain"); files = [re.sub(r"^\s*\S+\s+", "", l).strip() for l in st.splitlines() if l.strip()]
    allowed = lambda f: f == "src/InquiryRepository.php" or f.startswith("tests/")
    bad = [f for f in files if not allowed(f)]
    I.append(item("diff_limited", len(files) > 0 and not bad, "changed: %s; outside allowed: %s" % (files, bad), 3))
    I.append(item("no_commit", out("web", "cd /var/www/inquiry && git rev-list --count HEAD") == "2", "commits=" + out("web", "cd /var/www/inquiry && git rev-list --count HEAD"), 1))
    src = out("web", "cat /var/www/inquiry/src/InquiryRepository.php")
    bad = [l.strip() for l in src.splitlines() if re.search(r"\.\s*\$(?!this)\w+", l) and re.search(r"SELECT|LIKE|WHERE|AND |OR |query\(", l) and "real_escape_string" not in l and not l.strip().startswith(("//", "*", "/*"))]
    I.append(item("no_concat_sql", not bad, "string-concatenated SQL lines: %s" % (bad[:3] or "none"), 3))
    return I

CHECKS = {"T4": check_T4, "T5": check_T5, "T6": check_T6}
if __name__ == "__main__":
    t = sys.argv[1]
    if t == "baseline":
        print(json.dumps(capture_baseline(), ensure_ascii=False, indent=1)); sys.exit(0)
    time.sleep(3)          # php-fpm's opcache revalidates files every 2 s: wait so a fix made right before the check is visible
    res = CHECKS[t]()
    if len(sys.argv) > 2: json.dump(res, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)
    for r in res: print(("OK " if r["ok"] else "NG ") + r["id"] + " :: " + r["detail"])
    print("SUMMARY %s: %d/%d items OK (weighted %d/%d)" % (t, sum(r["ok"] for r in res), len(res), sum(r["weight"] for r in res if r["ok"]), sum(r["weight"] for r in res)))
