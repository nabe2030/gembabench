#!/usr/bin/env python3
"""Per-trial table and summary of finished trials (OpenCode 2.x rows), the way the published GembaBench v0.1 numbers were made.
usage: summarize_results.py --results <results dir> --config "<name>=<label>[,<label>...]" [--config ...] --out <dir>
  A trial directory is <date>-<time>_<task>_<label>_oc2_r<n>; directories with ABORTED in the name are skipped.
  Judge: result_rejudged_j14.json when present (rejudge.py <dir> j14), else result.json; T4-T6 scores are the live checks of the trial (check_items),
  replaced by check_items_rescored_j14.json when present. Wait = shell calls containing `sleep` that ran >= 30 s (wait_stats.py; computed here when the trial has no wait_stats.json, likewise the early-stop label). Ending: normal /
  time-cap (the task's time limit was hit) / early-stop:<type> (early_stop.py es2: the model ended without a deliverable) / no-deliverable.
Writes <out>/trials.csv and <out>/summary.md (median [min-max] per configuration and task)."""
import argparse, csv, glob, json, os, statistics as st, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import step_stats, wait_stats, early_stop
MAX = {"T1": 45, "T2": 8, "T3": 8, "T4": 31, "T5": 45, "T6": 23}
def num(s):
    try: return int(str(s).split("/")[0])
    except Exception: return None
def load(d):
    r = json.load(open(d + "/result.json")); p = d + "/result_rejudged_j14.json"
    if os.path.exists(p):
        rj = json.load(open(p))
        if r.get("check_items") and not rj.get("check_items"): rj["check_items"] = r["check_items"]
        for k in ("budget_proxy", "end_state"):
            if k in r and k not in rj: rj[k] = r[k]
        r = rj
    pr = d + "/check_items_rescored_j14.json"
    if os.path.exists(pr): r["check_items"] = json.load(open(pr))["items"]
    return r
def stats_any(d):
    """step_stats of a trial; a trial whose opencode.db is kept only as opencode.db.gz is read from a temporary copy (the trial dir is not changed)"""
    if os.path.exists(d + "/opencode.db") or not os.path.exists(d + "/opencode.db.gz"): return step_stats.stats(d)
    import tempfile, gzip, shutil
    with tempfile.TemporaryDirectory() as t:
        for f in os.listdir(d):
            if f != "opencode.db.gz": os.symlink(os.path.join(d, f), os.path.join(t, f))
        with gzip.open(d + "/opencode.db.gz") as src, open(t + "/opencode.db", "wb") as dst: shutil.copyfileobj(src, dst)
        return step_stats.stats(t)
def row(cfg, d):
    b = os.path.basename(d); t = b.split("_")[1]; rep = int(b.rsplit("_r", 1)[1]); r = load(d); c = r["conditions"]; rj = r.get("report_judge") or {}
    if t == "T1": score = num(rj.get("f1_weighted"))
    elif t == "T2": score = num(rj.get("f3_score"))
    elif t == "T3": score = num(rj.get("c_score"))
    else: ci = r.get("check_items") or []; score = sum(i["weight"] for i in ci if i["ok"]) if ci else None
    dur = (c.get("duration_sec") or 0) / 60.0; excl = dur
    try:
        w = json.load(open(d + "/wait_stats.json")) if os.path.exists(d + "/wait_stats.json") else wait_stats.stats(d)      # computed on the fly when wait_stats.py was not run
        if w.get("supported"): excl = w["duration_excl_wait_min"]
    except Exception: pass
    out_tok = None; note = ""
    try: out_tok = stats_any(d).get("out_tok")
    except Exception as e: note = "output tokens unavailable (%s)" % type(e).__name__
    es = {}
    try: es = json.load(open(d + "/early_stop_es2.json")) if os.path.exists(d + "/early_stop_es2.json") else (early_stop.analyse(d) or {})      # computed on the fly
    except Exception: pass
    deliv = (r.get("end_state") or {}).get("deliverable")
    if c.get("timed_out") or c.get("opencode_exit") == 124: end = "time-cap"
    elif es.get("early_stop"): end = "early-stop:%s" % es.get("stop_type")
    elif deliv is False: end = "no-deliverable"
    else: end = "normal"
    t3b = num((r.get("report_judge_t3b") or {}).get("t3b_points")) if t == "T3" else None
    return {"config": cfg, "task": t, "rep": rep, "score": score, "max_score": MAX[t], "t3b_points": t3b, "duration_min": round(dur, 1),
            "duration_excl_wait_min": round(excl, 1), "output_tokens": out_tok, "ending": end, "note": note}
def fmt(v):
    v = [x for x in v if x is not None]
    if not v: return "-"
    f = lambda x: "%g" % round(x, 1)
    return f(st.median(v)) if len(v) == 1 else "%s [%s–%s]" % (f(st.median(v)), f(min(v)), f(max(v)))
ap = argparse.ArgumentParser(); ap.add_argument("--results", required=True); ap.add_argument("--config", action="append", required=True); ap.add_argument("--out", required=True)
a = ap.parse_args(); os.makedirs(a.out, exist_ok=True); rows = []; names = []
for spec in a.config:
    name, labels = spec.split("=", 1); names.append(name)
    for lab in labels.split(","):
        for d in sorted(glob.glob(os.path.join(a.results, "2026*_T[1-6]_*_oc2_r[0-9]*"))):
            p = os.path.basename(d).split("_")
            if "ABORTED" in d or len(p) < 5 or p[2] != lab or not os.path.exists(d + "/result.json"): continue
            rows.append(row(name, d))
rows.sort(key=lambda x: (names.index(x["config"]), x["task"], x["rep"]))
with open(os.path.join(a.out, "trials.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
L = ["# Summary (median [min–max] over the repetitions)", "", "| Task | Metric | " + " | ".join(names) + " |", "|---|---|" + "---|" * len(names)]
for t in ("T1", "T2", "T3", "T4", "T5", "T6"):
    R = {n: [x for x in rows if x["config"] == n and x["task"] == t] for n in names}
    def line(label, fn): L.append("| %s | %s | %s |" % (t, label, " | ".join(fn(R[n]) if R[n] else "-" for n in names)))
    line("n", lambda X: str(len(X)))
    line("score (/%d)" % MAX[t], lambda X: fmt([x["score"] for x in X]))
    if t in ("T4", "T5", "T6"): line("full-score trials", lambda X: "%d/%d" % (sum(1 for x in X if x["score"] == MAX[t]), len(X)))
    if t == "T3": line("T3b points", lambda X: fmt([x["t3b_points"] for x in X]))
    line("duration (min)", lambda X: fmt([x["duration_min"] for x in X]))
    line("duration excl. waits (min)", lambda X: fmt([x["duration_excl_wait_min"] for x in X]))
    line("output tokens", lambda X: fmt([x["output_tokens"] for x in X]))
    line("endings other than normal", lambda X: ", ".join("r%d %s" % (x["rep"], x["ending"]) for x in X if x["ending"] != "normal") or "-")
open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8").write("\n".join(L) + "\n"); print(len(rows), "trials")
