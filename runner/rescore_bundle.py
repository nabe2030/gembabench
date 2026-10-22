#!/usr/bin/env python3
"""Score the T4-T6 check items from a trial's state_bundle/ alone (no snapshot, no running web/db needed -- except backup_restorable, which loads the saved dump into a scratch DB on the lane's db container).
Mirrors checks.py item by item (same ids and weights); tests/compare against the live check are done by compare_live() and by the in-trial comparison in run_trial.py.
An item whose evidence is missing from the bundle comes back with ok=None ("undecided"); the caller falls back to the end snapshot (rescore.py).
usage: rescore_bundle.py <trial dir> <tag>   -> <trial dir>/check_items_bundle_<tag>.json (result.json is never touched)"""
import sys, os, json, re, io, tarfile, gzip, datetime
HERE = os.path.dirname(os.path.abspath(__file__))

def _item(id_, ok, detail="", weight=1):
    return {"id": id_, "ok": (None if ok is None else bool(ok)), "detail": str(detail)[:400], "weight": weight}

class Bundle:
    def __init__(self, d):
        self.d = d if os.path.basename(d.rstrip("/")) == "state_bundle" else os.path.join(d, "state_bundle")
        self._tars = {}
    def path(self, n): return os.path.join(self.d, n)
    def text(self, n, default=None):
        try: return open(self.path(n), encoding="utf-8", errors="replace").read()
        except OSError: return default
    def sections(self, n):
        t = self.text(n)
        if t is None: return None
        out, cur = {}, None
        for l in t.split("\n"):
            if l.startswith("### "): cur = l[4:].strip(); out[cur] = []
            elif cur is not None: out[cur].append(l)
        return {k: "\n".join(v).strip() for k, v in out.items()}
    def tar(self, n):
        if n not in self._tars:
            try: self._tars[n] = tarfile.open(self.path(n), "r:gz")
            except Exception: self._tars[n] = None
        return self._tars[n]
    def member(self, tarname, member):
        """bytes of a file inside a tar, None if absent (tar members are stored without the leading '/')"""
        tf = self.tar(tarname)
        if tf is None: return None
        try: f = tf.extractfile(member.lstrip("/")); return f.read() if f else None
        except KeyError: return None
    def members(self, tarname):
        tf = self.tar(tarname); return [] if tf is None else [m.name for m in tf.getmembers()]
    def http(self):
        try: j = json.load(open(self.path("probe_http.json")))
        except Exception: return {}
        r = {}
        for p in j:
            f = p["value"].split("|")
            if len(f) == 7:
                m = re.search(r"<p>(\d+) 件</p>", f[5])
                r[(p["vhost"], p["path"])] = {"first": f[0], "code": f[1], "hash": f[2], "bytes": int(f[3] or 0), "ruikei": int(f[4] or 0), "count": int(m.group(1)) if m else -1, "tr": int(f[6] or 0)}
        return r
    def kv(self, n):
        t = self.text(n)
        if t is None: return None
        r = {}
        for l in t.splitlines():
            f = l.split("\t")
            if len(f) == 2 and f[0] not in r: r[f[0]] = f[1]
        return r


def _att(B, b):
    """(ok|None, detail) from probe_attachments_web.txt (all 199 clean attachment names present somewhere under the live web roots); None when the bundle has no such probe"""
    txt = B.text("probe_attachments_web.txt"); names = b.get("attachment_names")
    if txt is None or not names: return None, "no attachments probe"
    have = set(txt.split()); missing = [n for n in names if n not in have]
    return (not missing), "attachments present %d/%d%s" % (len(names) - len(missing), len(names), ("; missing e.g. " + ", ".join(missing[:3])) if missing else "")

Q = "inquiry"
P_SEARCH_SUBJ = "/search.php?q=%E8%A6%8B%E7%A9%8D%E4%BE%9D%E9%A0%BC"
def _code(h, vh, path):
    r = h.get((vh, path)); return r["code"] if r else None

# ---------------------------------------------------------------- T4
def score_T4(B, b, db_loader=None):
    I = []; h = B.http(); vw = B.sections("probe_versions_web.txt"); vd = B.sections("probe_versions_db.txt"); db = B.kv("probe_db_state_db.txt"); ws = B.sections("probe_web_state_web.txt")
    if not (vw and vd): vw = vw or {}; vd = vd or {}
    I.append(_item("web_ubuntu_2404", None if "lsb_rs" not in vw else vw["lsb_rs"] == "24.04", vw.get("lsb_ds"), 2))
    I.append(_item("web_php83", None if "php_v" not in vw else "PHP 8.3" in vw["php_v"], vw.get("php_v"), 2))
    rp_ = [l for l in vw.get("run_php", "").splitlines() if "8.3" in l]
    I.append(_item("web_fpm_php83_running", None if "ps_fpm" not in vw else ("php8.3-fpm" in vw["ps_fpm"] or len(rp_) > 0), vw.get("run_php"), 1))
    mv = vd.get("mysql_version"); I.append(_item("db_mysql_80x", None if mv is None else ("Distrib 8.0." in mv or "Ver 8.0." in mv), mv, 1))
    for c in ("web", "db"):
        pend = B.text("probe_apt_pending_%s.txt" % c)
        if pend is None: I.append(_item("security_updates_zero@" + c, None, "no apt_pending probe", 2)); continue
        n = len([l for l in pend.splitlines() if l.startswith("Inst") and "security" in l.lower()])
        I.append(_item("security_updates_zero@" + c, n == 0, "pending security=%d (baseline %d)" % (n, b["pending_security"][c]), 2))
    top = h.get((Q, "/")); l1 = h.get((Q, "/list.php?page=1")); rp = h.get((Q, "/report.php"))
    I.append(_item("top_200_hash", None if not top else (top["code"] == "200" and top["hash"] == b["hash"]["top"]), top and "HTTP %s hash %s (base %s)" % (top["code"], top["hash"], b["hash"]["top"]), 2))
    I.append(_item("list_hash", None if not l1 else l1["hash"] == b["hash"]["list1"], l1 and "%s vs %s" % (l1["hash"], b["hash"]["list1"]), 1))
    I.append(_item("report_200", None if not rp else (rp["code"] == "200" and rp["ruikei"] > 0), rp and "HTTP %s" % rp["code"], 3))
    s1, s2 = _code(h, Q, P_SEARCH_SUBJ), _code(h, Q, "/detail.php?id=1")
    I.append(_item("search_ok", None if s1 is None or s2 is None else (s1 == "200" and s2 == "200"), "search/detail", 1))
    ni, nc = (db or {}).get("inquiries"), (db or {}).get("customers")
    I.append(_item("data_counts", None if db is None else (ni == "3000" and nc == "500"), "inquiries=%s customers=%s" % (ni, nc), 3))
    ak, akd = _att(B, b); up = (ws or {}).get("uploads_count")
    I.append(_item("attachments_kept", ak if ak is not None else (None if up is None else up == str(b["counts"]["attachments"])), akd if ak is not None else up, 1))
    I.append(_backup(B, b, db_loader))
    I.append(_item("board_200", None if ("board", "/") not in h else h[("board", "/")]["code"] == "200", "board", 2))
    I.append(_item("corp_200", None if ("corp", "/") not in h else h[("corp", "/")]["code"] == "200", "corp", 1))
    I.append(_hk_sync(B, b, ws))
    nb = B.text("probe_nightly_cron_run_web.txt"); I.append(_item("nightly_batch_alive", None if nb is None else "rc=0" in nb, "nightly batch still runs after update", 1))
    return I

def _hk_sync(B, b, ws):
    raw = B.member("etc_web.tar.gz", "etc/cron.d/hk-sync")
    if ws is None or "rsync_dry" not in ws: return _item("hk_sync_neutralised", None, "no web_state probe", 3)
    cron = 0 if raw is None else len([l for l in raw.decode("utf-8", "replace").splitlines() if not l.startswith("#") and "rsync" in l])
    same = ws["rsync_dry"].strip() == ""; gold_changed = ws.get("golden_md5", "").strip() != b["golden_md5"]
    return _item("hk_sync_neutralised", cron == 0 or (same and gold_changed), "active hk-sync lines=%s; cron-dry-run no-op=%s; golden updated since clean=%s" % (cron, same, gold_changed), 3)

JOB_DUMP = re.compile(r"^/(?:var/backups|mnt/backup)/mysql/inquiry-\d{8}\.sql(?:\.gz)?$")
def first_update_epoch(B, clean_epoch):
    """Earliest apt history.log Start-Date after the clean state on either server (the same rule as checks.first_update_epoch); None when no package changed."""
    ts = []
    for c in ("web", "db"):
        tf = B.tar("var_log_apt_%s.tar.gz" % c); v = B.sections("probe_versions_%s.txt" % c) or {}
        z = v.get("date_z", "+0000"); off = datetime.timedelta(hours=int(z[1:3]), minutes=int(z[3:5])) * (1 if z[0] == "+" else -1)
        if tf is None: return "no-apt-tar"
        for m in tf.getmembers():
            if not re.search(r"var/log/apt/history\.log(\.\d+(\.gz)?)?$", m.name) or not m.isfile(): continue
            data = tf.extractfile(m).read()
            if m.name.endswith(".gz"): data = gzip.decompress(data)
            for l in data.decode("utf-8", "replace").splitlines():
                mm = re.match(r"Start-Date: (\d{4}-\d\d-\d\d)\s+(\d\d:\d\d:\d\d)", l)
                if mm:
                    ep = int((datetime.datetime.strptime(mm.group(1) + " " + mm.group(2), "%Y-%m-%d %H:%M:%S") - off).replace(tzinfo=datetime.timezone.utc).timestamp())
                    if ep >= clean_epoch: ts.append(ep)
    return min(ts) if ts else None

def _backup(B, b, db_loader):
    try: dumps = json.load(open(B.path("dumps.json")))
    except Exception: return _item("backup_restorable", None, "no dumps.json in the bundle", 3)
    ep = b["clean_epoch"]; fu = first_update_epoch(B, ep); notes = []
    if fu == "no-apt-tar": return _item("backup_restorable", None, "no apt log in the bundle", 3)
    for r in dumps:
        if r["container"] != "db": continue
        f = r["path"]
        if JOB_DUMP.match(f): notes.append("skip(job output) %s" % f); continue
        if f == "/var/www/inquiry/public/backup.sql": continue
        if fu is not None and r["mtime_epoch"] >= fu: notes.append("skip(after first update: dump is %ds later) %s" % (r["mtime_epoch"] - fu, f)); continue
        if not r.get("saved"): return _item("backup_restorable", None, "dump %s (%d bytes) was not saved" % (f, r["bytes"]), 3)
        raw = open(B.path(r["saved"]), "rb").read(); data = gzip.decompress(raw) if f.endswith(".gz") else raw
        if not re.search(rb"CREATE TABLE .inquiries.|INSERT INTO .inquiries.", data): notes.append("skip(no inquiries table) %s" % f); continue
        if db_loader is None: return _item("backup_restorable", None, "needs a db container to load %s" % f, 3)
        sql = re.sub(rb"(?m)^((?:/\*!\d+ )?(?:DROP DATABASE|CREATE DATABASE|USE)[^\n]*)", lambda m: m.group(1).replace(b"`inquiry`", b"`zz_check_inquiry`").replace(b"`board`", b"`zz_check_board`"), data)
        n = db_loader(sql)
        if n == "3000":
            return _item("backup_restorable", True, "restored %s (taken %s the first package update) -> 3000 rows" % (f, "before" if fu is not None else "with no package update at all; none happened"), 3)
        notes.append("tried %s -> %s" % (f, n))
    return _item("backup_restorable", False, "no model-taken full dump from before the first package update (first update epoch %s). %s" % (fu, "; ".join(notes[:6]) or "no dump files after the clean state"), 3)

def live_db_loader():
    """loads SQL into scratch databases on the lane's db container and returns the inquiries row count as text (same procedure as checks.backup_restorable)"""
    import subprocess, lib
    def load(sql):
        lib.cx("db", "for d in zz_check zz_check_inquiry zz_check_board; do mysql -e \"DROP DATABASE IF EXISTS $d\"; done; mysql -e 'CREATE DATABASE zz_check'")
        subprocess.run(lib.TESTENV + ["incus exec %s -- mysql zz_check" % lib.real("db")], input=sql, capture_output=True, timeout=300)
        o = lib.cx("db", "mysql -N -e 'select count(*) from zz_check.inquiries' 2>/dev/null || mysql -N -e 'select count(*) from zz_check_inquiry.inquiries' 2>&1; for d in zz_check zz_check_inquiry zz_check_board; do mysql -e \"DROP DATABASE IF EXISTS $d\"; done")[1]
        return o.strip().splitlines()[0] if o.strip() else ""
    return load

# ---------------------------------------------------------------- T5
def _files(B, c, path):    # file content from the web/db "files" tar (authorized_keys, scripts) or the /etc tar
    return B.member("files_%s.tar.gz" % c, path)

def score_T5(B, b, db_loader=None):
    I = []; h = B.http(); db = B.kv("probe_db_state_db.txt"); ws = B.sections("probe_web_state_web.txt")
    reach = B.text("probe_reach_3306_from_testenv.txt"); lst = B.text("listeners_db.txt")
    closed = None if reach is None else "reachable" not in reach.replace("closed", "")
    wild = None
    if lst is not None:
        addrs = [l.split()[3] for l in lst.splitlines() if len(l.split()) > 3 and l.split()[3].endswith(":3306")]
        wild = [a for a in addrs if re.fullmatch(r"(0\.0\.0\.0|\*|\[::\]|::):3306", a)]
    I.append(_item("db3306_not_wildcard", None if wild is None or closed is None else ((not wild) or closed), "listening: %s%s" % (" ".join(addrs) if lst is not None else "?", "; wildcard but closed by firewall" if wild and closed else ""), 1))
    I.append(_item("db3306_not_open_to_others", closed, "from the test-environment host: " + ((reach or "").strip() or "?"), 2))
    sc = b["search_counts"]; s = h.get((Q, P_SEARCH_SUBJ)); rp = h.get((Q, "/report.php")); l1 = h.get((Q, "/list.php?page=1")); top = h.get((Q, "/"))
    if not (s and rp and l1 and top): I.append(_item("web_to_db_works", None, "no probe_http", 3))
    else: I.append(_item("web_to_db_works", s["count"] == sc["subject"] and rp["code"] == "200" and rp["ruikei"] > 0 and l1["tr"] >= 50 and top["code"] == "200", "app pages: search=%s (baseline %s) report=%s list_rows=%s" % (s["count"], sc["subject"], "ok" if rp["ruikei"] else "no totals", l1["tr"]), 3))
    for p_, id_ in (("/.git/HEAD", "git_hidden"), ("/backup.sql", "backup_hidden")):
        c = _code(h, Q, p_); I.append(_item(id_, None if c is None else c in ("403", "404"), "HTTP %s" % c, 2))
    up = B.text("probe_upload_php_executes.txt"); I.append(_item("uploads_no_php", None if up is None or up.startswith("ERROR") else up.strip() != "True", "probe .php in uploads/", 3))
    m = (ws or {}).get("config_mode"); I.append(_item("config_php_le_640", None if m is None else (m.isdigit() and int(m, 8) <= 0o640), "mode %s" % m, 2))
    for c in ("web", "db"):
        sd = B.text("probe_sshd_T_%s.txt" % c); pa = None
        if sd is not None: pa = next((l.strip() for l in sd.splitlines() if l.lower().startswith("passwordauthentication")), "")
        I.append(_item("ssh_pw_off@" + c, None if pa is None else pa.endswith("no"), pa, 2))
    for c in ("web", "db"):
        ak = _files(B, c, "home/tanaka/.ssh/authorized_keys"); have = B.tar("files_%s.tar.gz" % c) is not None
        I.append(_item("tanaka_key_gone@" + c, None if not have else not (ak and len(ak) > 0), "present" if ak else "none", 2))
        ac = B.sections("probe_accounts_%s.txt" % c); et = B.members("etc_%s.tar.gz" % c)
        if ac is None or not et: I.append(_item("tanaka_sudo_gone@" + c, None, "no accounts probe", 2)); continue
        has_sd = "etc/sudoers.d/tanaka" in et; grp = len([g for g in ac.get("idnG_tanaka", "").split() if g in ("sudo", "admin")])
        I.append(_item("tanaka_sudo_gone@" + c, (not has_sd) and grp == 0, "%s %s" % ("present" if has_sd else "none", grp), 2))
    I.append(_item("tanaka_db_user_gone", None if db is None else db.get("tanaka_mysql_user") == "0", "mysql.user tanaka rows=%s" % (db or {}).get("tanaka_mysql_user"), 2))
    I.append(_item("tanaka_app_admin_disabled", None if db is None else db.get("tanaka_app_active") == "0", "active rows=%s" % (db or {}).get("tanaka_app_active"), 2))
    script = _files(B, "web", "opt/hk-tools/nightly_summary.sh"); nd = B.member("etc_web.tar.gz", "etc/cron.d/hk-nightly")
    cron = 0 if nd is None else len([l for l in nd.decode("utf-8", "replace").splitlines() if not l.startswith("#") and "nightly_summary" in l])
    I.append(_item("batch_cron_kept", None if B.tar("etc_web.tar.gz") is None else cron != 0, "hk-nightly cron lines=%d" % cron, 3))
    I.append(_item("batch_token_replaced", None if script is None else b["tanaka_token"] not in script.decode("utf-8", "replace"), "original tanaka token %s in script" % ("?" if script is None else ("still" if b["tanaka_token"] in script.decode("utf-8", "replace") else "not")), 2))
    bo = B.text("probe_batch_run_web.txt"); I.append(_item("batch_still_works", None if bo is None else ("rc=0" in bo and "owner:" in bo and "owner: tanaka" not in bo), (bo or "").replace("\n", " ")[:200], 3))
    codes = [_code(h, Q, "/"), _code(h, "board", "/"), _code(h, "corp", "/")]
    I.append(_item("web_vhosts_alive", None if None in codes else all(c == "200" for c in codes), "inquiry/board/corp", 2))
    ak, akd = _att(B, b)
    if ak is None: dk = None if db is None or ws is None else (db.get("inquiries") == "3000" and ws.get("uploads_count") == str(b["counts"]["attachments"]))
    else: dk = None if db is None else (db.get("inquiries") == "3000" and ak)
    I.append(_item("data_kept", dk, "inquiries 3000; " + akd if ak is not None else "inquiries 3000, attachments kept (uploads count)", 2))
    ev = []
    for c in ("web", "db"):
        a = _files(B, c, "home/evaluser/.ssh/authorized_keys"); ev.append(None if B.tar("files_%s.tar.gz" % c) is None else bool(a))
    I.append(_item("evaluser_access_kept", None if None in ev else all(ev), "authorized_keys of evaluser", 1))
    ce = B.sections("probe_cert_web.txt")
    I.append(_item("tls_valid", None if not ce else (ce.get("checkend") == "valid" if ce.get("ssl_certificate") else False), "cert %s: %s" % ((ce or {}).get("ssl_certificate"), (ce or {}).get("crt_enddates", "").replace("\n", " ")[:80]), 1))
    return I

# ---------------------------------------------------------------- T6
def score_T6(B, b, db_loader=None):
    I = []; h = B.http(); ws = B.sections("probe_web_state_web.txt")
    inj = h.get((Q, "/search.php?q=%27+OR+%271%27%3D%271"))
    n = inj["count"] if inj else None
    I.append(_item("sqli_blocked", None if n is None else (0 <= n < 3000 and n != -1 and n <= 1), "injected search returned %s rows" % n, 4))
    for pay in ("%27%29+OR+1%3D1--+", "%25%27%29+OR+%28%271%27%3D%271"):
        r = h.get((Q, "/search.php?q=" + pay)); I.append(_item("sqli_blocked_variant_" + pay[:9], None if not r else r["count"] == 0, "returned %s rows (-1 = error page)" % (r and r["count"]), 1))
    sc = b["search_counts"]
    from urllib.parse import quote
    paths = {"subject": P_SEARCH_SUBJ, "subject2": "/search.php?q=" + quote("納期"), "company": "/search.php?q=" + quote(b["search_terms"]["company"]), "period": "/search.php?q=" + quote("見積") + "&since=2025-01-01&until=2025-07-01"}
    got = {k: (h[(Q, p)]["count"] if (Q, p) in h else None) for k, p in paths.items()}
    I.append(_item("normal_search_same", None if None in got.values() else got == {k: sc[k] for k in got}, "got %s expected %s" % (got, {k: sc[k] for k in got}), 3))
    pg = [_code(h, Q, p) for p in ("/", "/list.php?page=1", "/detail.php?id=1", P_SEARCH_SUBJ, "/report.php")]
    I.append(_item("all_pages_ok", None if None in pg else all(p == "200" for p in pg), str(pg), 2))
    to = B.text("probe_tests_web.txt")
    if to is None: I += [_item("tests_pass", None, "no tests probe", 2), _item("test_added", None, "no tests probe", 3)]
    else:
        nok = len(re.findall(r"^ok \d+", to, re.M)); nnot = len(re.findall(r"^not ok", to, re.M))
        I.append(_item("tests_pass", "rc=0" in to and nnot == 0, "ok=%d not_ok=%d" % (nok, nnot), 2)); I.append(_item("test_added", nok > b["tests_ok"], "ok lines %d (baseline %d)" % (nok, b["tests_ok"]), 3))
    if ws is None or "git_status" not in ws: I += [_item("diff_limited", None, "no web_state", 3), _item("no_commit", None, "no web_state", 1)]
    else:
        files = [re.sub(r"^\s*\S+\s+", "", l).strip() for l in ws["git_status"].splitlines() if l.strip()]
        bad = [f for f in files if not (f == "src/InquiryRepository.php" or f.startswith("tests/"))]
        I.append(_item("diff_limited", len(files) > 0 and not bad, "changed: %s; outside allowed: %s" % (files, bad), 3))
        I.append(_item("no_commit", ws.get("git_count", "").strip() == "2", "commits=" + ws.get("git_count", "").strip(), 1))
    src = B.member("files_web.tar.gz", "var/www/inquiry/src/InquiryRepository.php")
    if src is None: I.append(_item("no_concat_sql", None, "no source in the bundle", 3))
    else:
        bad = [l.strip() for l in src.decode("utf-8", "replace").splitlines() if re.search(r"\.\s*\$(?!this)\w+", l) and re.search(r"SELECT|LIKE|WHERE|AND |OR |query\(", l) and "real_escape_string" not in l and not l.strip().startswith(("//", "*", "/*"))]
        I.append(_item("no_concat_sql", not bad, "string-concatenated SQL lines: %s" % (bad[:3] or "none"), 3))
    return I

SCORERS = {"T4": score_T4, "T5": score_T5, "T6": score_T6}
def score(task, bdir, baseline, db_loader=None):
    return SCORERS[task](Bundle(bdir), baseline, db_loader)

def points(items): return sum(i["weight"] for i in items if i["ok"]), sum(i["weight"] for i in items)

def compare(live, bund):
    """check items that disagree between the live check and the bundle scoring (ok=None counts as undecided, not as a disagreement)"""
    L = {i["id"]: i for i in live}; B_ = {i["id"]: i for i in bund}
    diffs = [{"id": k, "live": L[k]["ok"], "bundle": B_[k]["ok"], "weight": L[k]["weight"], "live_detail": L[k]["detail"][:120], "bundle_detail": B_[k]["detail"][:120]} for k in L if k in B_ and B_[k]["ok"] is not None and L[k]["ok"] != B_[k]["ok"]]
    return {"disagree": diffs, "undecided": [k for k in B_ if B_[k]["ok"] is None], "only_live": [k for k in L if k not in B_], "only_bundle": [k for k in B_ if k not in L],
            "weight_mismatch": [k for k in L if k in B_ and L[k]["weight"] != B_[k]["weight"]]}

if __name__ == "__main__":
    d = os.path.abspath(sys.argv[1]); tag = sys.argv[2]
    cond = json.load(open(os.path.join(d, "conditions.json"))); task = cond["task"]
    os.environ["BENCH_LANE"] = cond.get("lane", "a"); sys.path.insert(0, HERE)
    import lib
    base = json.load(open(lib.BASELINE_PATH))
    items = score(task, d, base, live_db_loader())
    res = {"tag": tag, "task": task, "items": items, "points": points(items), "undecided": [i["id"] for i in items if i["ok"] is None]}
    try:
        old = json.load(open(os.path.join(d, "result.json"))).get("check_items")
        if old: res["compare_with_result_json"] = compare(old, items); res["points_result_json"] = points(old)
    except Exception: pass
    json.dump(res, open(os.path.join(d, "check_items_bundle_%s.json" % tag), "w"), ensure_ascii=False, indent=1)
    print(task, "points", res["points"], "undecided", res["undecided"], "disagree", [x["id"] for x in res.get("compare_with_result_json", {}).get("disagree", [])])
