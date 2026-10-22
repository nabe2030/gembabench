#!/usr/bin/env python3
"""Per-trial step statistics (read-only on opencode.db + events.jsonl; works for OpenCode 1.x and 2.x).
Per assistant step: generation time (1.x: completed-created; 2.x: streamed-created), output tokens (events step_finish), reasoning chars, finish reason.
usage: step_stats.py <trialdir>...  -> markdown table; stats(d) -> dict"""
import sqlite3, json, sys, os, statistics as st
def _steps(d):
    db = sqlite3.connect("file:%s?mode=ro" % os.path.join(d, "opencode.db"), uri=True)
    tabs = {r[0] for r in db.execute("select name from sqlite_master where type='table'")}
    out = []
    if "session_message" in tabs and "message" not in tabs:           # 2.x
        for (data,) in db.execute("select data from session_message where type='assistant' order by seq"):
            m = json.loads(data); t = m.get("time", {})
            end = t.get("streamed") or t.get("completed")
            if not (t.get("created") and end): continue
            rs = sum(len(c.get("text", "")) for c in m.get("content", []) if c.get("type") == "reasoning")
            out.append({"gen": (end - t["created"]) / 1000, "reason": rs, "finish": m.get("finish")})
    else:                                                              # 1.x
        parts = {}
        for data, mid in db.execute("select data,message_id from part"):
            p = json.loads(data)
            if p["type"] == "reasoning": parts[mid] = parts.get(mid, 0) + len(p.get("text", ""))
        for mid, data in db.execute("select id,data from message order by time_created"):
            m = json.loads(data)
            if m.get("role") != "assistant" or not m.get("time", {}).get("completed"): continue
            out.append({"gen": (m["time"]["completed"] - m["time"]["created"]) / 1000, "reason": parts.get(mid, 0), "finish": m.get("finish"), "out1": m["tokens"]["output"]})
    return out
def stats(d):
    S = _steps(d)
    ev = [json.loads(l) for l in open(os.path.join(d, "events.jsonl"))]
    fin = [e["part"] for e in ev if e["type"] == "step_finish"]
    toks = [f.get("tokens", {}).get("output", 0) for f in fin]; reasons = [f.get("reason") for f in fin]
    inp = [f.get("tokens", {}).get("input", 0) + f.get("tokens", {}).get("cache", {}).get("read", 0) for f in fin]
    wall = (ev[-1]["timestamp"] - ev[0]["timestamp"]) / 1000 if ev else 0
    gsum = sum(s["gen"] for s in S); osum = sum(toks)
    gen = [s["gen"] for s in S]
    return dict(steps=len(fin), wall_min=round(wall / 60, 1), gen_min=round(gsum / 60, 1), step_med_s=round(st.median(gen), 1) if gen else 0, step_max_s=round(max(gen), 0) if gen else 0,
                out_tok=osum, tok_per_s=round(osum / gsum, 1) if gsum else 0, out_max=max(toks or [0]), finish_length=sum(1 for r in reasons if r == "length"), out_ge_16k=sum(1 for o in toks if o >= 16000),
                reason_chars=sum(s["reason"] for s in S), reason_max=max([s["reason"] for s in S] or [0]), last_input=inp[-1] if inp else 0, steps_over_300s=sum(1 for g in gen if g > 300))
if __name__ == "__main__":
    first = True
    for d in sys.argv[1:]:
        s = stats(d)
        if first: print("| trial | " + " | ".join(s) + " |"); print("|" + "---|" * (len(s) + 1)); first = False
        print("| %s | " % os.path.basename(d.rstrip("/"))[:58] + " | ".join(str(v) for v in s.values()) + " |")
