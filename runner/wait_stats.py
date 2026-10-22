#!/usr/bin/env python3
"""how much of a trial's wall time is the model WAITING on purpose (sleep), so durations can be shown with and without the waits.
Definition of a wait: a shell tool call (OpenCode 2.x, opencode.db) whose command contains `sleep` and whose execution (state time `ran` -> `completed`) lasted at least 30 s. The whole execution time of such a call counts as wait
(calls like `sleep 180; ssh target 'tail ...'` are almost entirely the sleep). Calls interrupted by the watchdog/cap count up to the moment they were interrupted. T3: only calls before stage 2 (the T3 duration is stage 1).
usage: wait_stats.py <trial dir>...  -> <trial dir>/wait_stats.json"""
import sqlite3, json, sys, os, re
SLEEP = re.compile(r"\bsleep\b")
CRON_HINT = re.compile(r"hk-sync|cron|golden|:15|date\s+\+%M|rsync|\b15:\d\d", re.I)
def stats(d):
    c = json.load(open(os.path.join(d, "conditions.json")))
    s2 = (c.get("stage2") or {}).get("start_epoch_ms")
    db = sqlite3.connect("file:%s?mode=ro" % os.path.join(d, "opencode.db"), uri=True)
    tabs = {r[0] for r in db.execute("select name from sqlite_master where type='table'")}
    if "session_message" not in tabs: return {"supported": False, "note": "not an OpenCode 2.x database"}
    calls = []
    for (data,) in db.execute("select data from session_message order by seq"):
        m = json.loads(data)
        rs = " ".join((x.get("text") or "") for x in m.get("content", []) if x.get("type") == "reasoning").strip().replace("\n", " ")
        for ct in m.get("content", []):
            if ct.get("type") != "tool" or ct.get("name") not in ("shell", "bash"): continue
            st = ct.get("state") or {}; cmd = (st.get("input") or {}).get("command") or ""; t = st.get("time") or ct.get("time") or {}
            if not (SLEEP.search(cmd) and t.get("ran") and t.get("completed")): continue
            dur = (t["completed"] - t["ran"]) / 1000.0
            if dur < 30: continue
            if s2 and t["ran"] >= s2: continue
            calls.append({"ran_ms": t["ran"], "seconds": round(dur, 1), "status": st.get("status"), "interrupted": (st.get("error") or {}).get("type") == "aborted", "cron_hint": bool(CRON_HINT.search(cmd + " " + rs)), "command": cmd[:200].replace("\n", " "), "reason_excerpt": rs[:260]})
    wait = round(sum(x["seconds"] for x in calls), 1)
    return {"supported": True, "wait_seconds": wait, "wait_minutes": round(wait / 60, 1), "calls": len(calls), "longest_seconds": max([x["seconds"] for x in calls] or [0]), "wait_calls": calls,
            "duration_min": round(c.get("duration_sec", 0) / 60, 1), "duration_excl_wait_min": round(max(0, c.get("duration_sec", 0) - wait) / 60, 1)}
if __name__ == "__main__":
    for d in sys.argv[1:]:
        try: r = stats(d.rstrip("/"))
        except Exception as e: r = {"supported": False, "error": "%s: %s" % (type(e).__name__, e)}
        json.dump(r, open(os.path.join(d, "wait_stats.json"), "w"), ensure_ascii=False, indent=1)
        print(os.path.basename(d.rstrip("/"))[:56], "|", r.get("duration_min"), "min | wait", r.get("wait_minutes"), "min | excl", r.get("duration_excl_wait_min"), "| calls", r.get("calls"), "| longest", r.get("longest_seconds"))
