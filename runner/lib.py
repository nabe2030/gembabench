"""Shared helpers for the agent-bench runner (runs on the runner host)."""
import subprocess, shlex, json, os, time, re, datetime, hashlib
try:
    from zoneinfo import ZoneInfo
    JST = ZoneInfo("Asia/Tokyo")
except Exception:                                           # pragma: no cover
    JST = datetime.timezone(datetime.timedelta(hours=9))

HOME = os.path.expanduser("~")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))          # repository root (runner/, scenario-01/, budget_proxy/)
CONF = json.load(open(os.environ.get("GEMBA_CONF") or os.path.join(ROOT, "gemba.conf.json")))   # copy gemba.conf.example.json and fill in your values
RESULTS = os.path.expanduser(CONF.get("results_dir", "~/gemba-results"))
# ssh to the test-environment host (the Incus host of the web/db containers); commands there run as an admin user with passwordless sudo/incus
TESTENV = ["ssh", "-i", os.path.expanduser(CONF["testenv"]["ssh_key"]), "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10", CONF["testenv"]["ssh_target"]]
RUNNER_OWNER = "%d:%d" % (os.getuid(), os.getgid())                         # owner of the files copied out of the subject's environment
VHOST_INQ = "inquiry.hiiragi-kinzoku.example"
VHOST_BOARD = "board.hiiragi-kinzoku.example"
# --- lanes : BENCH_LANE=a|b selects the web/db pair, bridge addresses, meta/baseline files. Code keeps the logical names "web"/"db"; real() maps them.
LANE = os.environ.get("BENCH_LANE", "a")
LANES = {k: dict(dict(web="web", db="db", web_ip="10.92.0.11", db_ip="10.92.0.12", gw="10.92.0.1", out="out", baseline="baseline.json", oc="subject", sfx="", subject_addr_prefix="10.0."), **v)
         for k, v in (CONF.get("lanes") or {"a": {}}).items()}            # one lane is enough; a second lane needs its own web/db pair, subject container and baseline
LN = LANES[LANE]; WEB_IP = LN["web_ip"]; DB_IP = LN["db_ip"]
RUNNER_DIR = os.path.dirname(os.path.abspath(__file__))
META_PATH = os.path.join(ROOT, "scenario-01", LN["out"], "meta.json")
BASELINE_PATH = os.path.join(RUNNER_DIR, LN["baseline"])
CONTAINERS = ("web", "db")
def real(c): return LN[c] if c in ("web", "db") else c

def now_jst():
    return datetime.datetime.now(JST)

def jst_str(d=None):
    return (d or now_jst()).strftime("%Y-%m-%d %H:%M:%S")

def sh(cmd, timeout=300):
    """Run a command line on the test-environment host as admin. Returns (rc, stdout, stderr)."""
    try:
        r = subprocess.run(TESTENV + [cmd], capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"

def cx(container, cmd, timeout=300):
    """Run bash -c <cmd> inside a container (root) via the test-environment host."""
    return sh("incus exec %s -- bash -c %s" % (real(container), shlex.quote(cmd)), timeout)

def out(container, cmd, timeout=300):
    return cx(container, cmd, timeout)[1].strip()

# follow redirects (HTTP->HTTPS is a legitimate hardening step), accept the self-signed certificate, and send every redirected host back to the local server
CURL_FOLLOW = "-L -k --max-redirs 3 --connect-to ::127.0.0.1:"
def http_code(path, host=VHOST_INQ, container="web", extra=""):
    # the URL is shell-quoted (an unquoted '&' would cut off query parameters such as since/until)
    return out(container, "curl -s -o /dev/null -m 20 %s -w '%%{http_code}' -H 'Host: %s' %s %s" % (CURL_FOLLOW, host, extra, shlex.quote("http://127.0.0.1" + path)))

def http_body(path, host=VHOST_INQ, container="web", extra=""):
    return cx(container, "curl -s -m 60 %s -H 'Host: %s' %s %s" % (CURL_FOLLOW, host, extra, shlex.quote("http://127.0.0.1" + path)))[1]

def http_hash(path, host=VHOST_INQ):
    return out("web", "curl -s -m 60 %s -H 'Host: %s' %s | sha256sum | cut -c1-16" % (CURL_FOLLOW, host, shlex.quote("http://127.0.0.1" + path)))

def item(id_, ok, detail="", weight=1):
    return {"id": id_, "ok": bool(ok), "detail": str(detail)[:400], "weight": weight}

def load_yaml(path):
    import yaml
    return yaml.safe_load(open(path, encoding="utf-8"))

def wait_ssh(container, ip, tries=60):
    for _ in range(tries):
        rc, o, _ = sh("nc -z -w2 %s 22 && echo up" % ip)
        if "up" in o: return True
        time.sleep(2)
    return False

def restore_clean(timeout=300):
    """Stop both containers, restore `clean`, start, and wait until web answers 200 and mysql accepts connections."""
    t0 = time.time()
    W, D = real("web"), real("db")
    sh("incus stop %s %s --force 2>&1; incus snapshot restore %s clean && incus snapshot restore %s clean && incus start %s %s" % (W, D, W, D, D, W), timeout)
    ok = False
    for _ in range(90):
        if http_code("/") == "200" and out("db", "mysql -N -e 'select 1' 2>/dev/null") == "1":
            ok = True; break
        time.sleep(2)
    return ok, round(time.time() - t0, 1)
