#!/usr/bin/env python3
"""Run a fixed series of trials one after another. Stops at the first abnormal event and writes
<results_dir>/series_status.json so the operator can report and wait (on a model-server problem, stop and leave the model server alone).
Abnormal = runner abort/exception, watchdog (no_start/stalled), opencode exit other than 0 or 124 (max-minutes cap is recorded, not abnormal)."""
import json, os, subprocess, sys, time, glob
from lib import *
HERE = os.path.dirname(os.path.abspath(__file__)); RES = RESULTS
label = sys.argv[1]; body = sys.argv[2]; maxmin = sys.argv[3]; lim_out = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != "-" else None
N = int(sys.argv[5]) if len(sys.argv) > 5 else 1
# N repetitions; within a repetition the tasks in order (and the harnesses in order, when several are given)
# SERIES_TASKS="T4,T5,T6" selects other tasks; SERIES_MAXMIN="T4=240,T5=150,T6=120" overrides the cap per task (default: the maxmin argument for all)
TASKS = tuple((os.environ.get("SERIES_TASKS") or "T1,T2,T3").split(","))
MAXMIN = dict(kv.split("=") for kv in (os.environ.get("SERIES_MAXMIN") or "").split(",") if kv)
START_N = int(os.environ.get("SERIES_START_N") or 1)      # SERIES_START_N=2: repetitions 2..N only
# the default harness is OpenCode 2.x (oc2) only; SERIES_HARNESS="oc1,oc2" brings back both. SERIES_SKIP="T1:1:oc2,..." (task:repetition:harness) leaves out trials that already exist.
HARNESSES = tuple((os.environ.get("SERIES_HARNESS") or "oc2").split(","))
SKIP = set((os.environ.get("SERIES_SKIP") or "").split(","))
SEQ = [(h, t, n) for n in range(START_N, N + 1) for t in TASKS for h in HARNESSES if "%s:%d:%s" % (t, n, h) not in SKIP]
status = {"label": label, "body": body, "started_jst": jst_str(), "done": [], "current": None, "stopped": None, "finished": False}
def save(): json.dump(status, open(os.path.join(RES, "series_status.json" if LANE == "a" else "series_status_%s.json" % LANE), "w"), ensure_ascii=False, indent=1)
# SERIES_EXPECT_MODEL="<base url>=<model id>" checks /v1/models before every trial; SERIES_THERMAL_GATE=<path of a gate script> runs it before every trial (optional; not included in this repository: any script that waits until the hardware is cool enough and exits non-zero to stop).
# Either failing stops the series (exit 4) without starting the trial; gate exit 10/11/20 is never retried or cleared here. SERIES_STATUS_CMD=<shell command> records its output (e.g. the model server's mode).
EXPECT = os.environ.get("SERIES_EXPECT_MODEL", ""); GATE = os.environ.get("SERIES_THERMAL_GATE", ""); STKEY = os.environ.get("SERIES_STATUS_CMD", "")      # optional shell command whose output (e.g. the model server's mode) is recorded before every trial
def pretrial(tag):
    pre = {"jst": jst_str()}
    if STKEY:
        try: pre["model_server_status"] = subprocess.run(STKEY, shell=True, capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL).stdout.strip()[-300:]
        except Exception as e: pre["model_server_status"] = "error: %s" % e
    if EXPECT:
        base, mid = EXPECT.rsplit("=", 1)
        try: pre["models"] = [m["id"] for m in json.load(urllib.request.urlopen(base.rstrip("/") + "/models", timeout=15)).get("data", [])]
        except Exception as e: pre["models"] = "error: %s" % e
        if not isinstance(pre["models"], list) or mid not in pre["models"]: return pre, "model check: %s not in %s" % (mid, pre["models"])
    if GATE:
        wf = os.path.join(RES, "thermal_gate_%s.json" % tag)
        g = subprocess.run([sys.executable, "-I", GATE, "--by", "gembabench-runner", "--wait-file", wf], stdin=subprocess.DEVNULL)
        try: pre["thermal_gate"] = json.load(open(wf))
        except Exception: pre["thermal_gate"] = {"exit_code": g.returncode, "result": "no wait-file"}
        pre["thermal_gate_rc"] = g.returncode; pre["thermal_waited_sec"] = pre["thermal_gate"].get("waited_sec")
        if g.returncode != 0: return pre, "thermal gate exit %d (%s): stop and report, do not clear" % (g.returncode, pre["thermal_gate"].get("result"))
    return pre, None
import urllib.request
for h, t, n in SEQ:
    if EXPECT or GATE or STKEY:
        pre, why = pretrial("%s_%s_r%d" % (t, h, n)); status["last_pretrial"] = pre
        if why:
            status["stopped"] = {"reason": "pretrial: " + why, "at": "%s %s r%d (not started)" % (h, t, n), "jst": jst_str()}; save(); sys.exit(4)
    else: pre = None
    status["current"] = {"harness": h, "task": t, "trial": n, "started_jst": jst_str()}; save()
    before = set(glob.glob(os.path.join(RES, "2026*_%s_%s_%s_r%d" % (t, label, h, n))))
    p = subprocess.run([sys.executable, os.path.join(HERE, "run_trial.py"), "--task", t, "--label", label, "--body", body, "--harness", h, "--trial", str(n), "--max-minutes", MAXMIN.get(t, maxmin)] + (["--limit-output", lim_out] if lim_out else []), cwd=HERE)
    new = sorted(set(glob.glob(os.path.join(RES, "2026*_%s_%s_%s_r%d" % (t, label, h, n)))) - before)
    d = new[-1] if new else None; cond = {}
    if d and os.path.exists(os.path.join(d, "conditions.json")): cond = json.load(open(os.path.join(d, "conditions.json")))
    rec = {"harness": h, "task": t, "trial": n, "stage2": cond.get("stage2"), "dir": os.path.basename(d) if d else None, "rc": p.returncode, "duration_sec": cond.get("duration_sec"), "opencode_exit": cond.get("opencode_exit"), "watchdog": cond.get("watchdog"), "timed_out": cond.get("timed_out"), "ended_jst": jst_str(), **({"pretrial": pre} if pre else {})}
    status["done"].append(rec); status["current"] = None
    s2 = cond.get("stage2") or {}
    bad = p.returncode != 0 or s2.get("watchdog") or s2.get("skipped") or cond.get("watchdog") or (cond.get("opencode_exit") not in (0, 124)) or not cond
    capped = cond.get("opencode_exit") == 124 or cond.get("timed_out") or (s2.get("opencode_exit") == 124)      # the max-minutes cap stops the series (for the operator's decision)
    if capped and not bad:
        status["stopped"] = {"reason": "time-cap: opencode hit the max-minutes cap (exit 124); series stopped for the operator's decision (cap is not an infrastructure fault)", "at": "%s %s r%d" % (h, t, n), "jst": jst_str()}; save(); sys.exit(3)
    if bad:
        status["stopped"] = {"reason": "abnormal: rc=%s watchdog=%s opencode_exit=%s" % (p.returncode, cond.get("watchdog"), cond.get("opencode_exit")), "at": "%s %s" % (h, t), "jst": jst_str()}; save(); sys.exit(2)
    save()
status["finished"] = True; status["ended_jst"] = jst_str(); save()
