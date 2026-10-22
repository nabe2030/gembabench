#!/usr/bin/env python3
"""how did each trial end? (records only: opencode.db, events.jsonl, result.json). usage: early_stop.py <results-root> <out.md> [out.json]
Per trial: last step's ending (tool / text / reasoning-only / empty), finish_reason, deliverable present, context use (input+cache_read tokens of the last step and the max, vs 262144),
compaction in the session (2.x 'compaction' message), whether the step before the last hit the output cap (finish=length) or the thinking budget (8192, reasoning ended with the 'thought about this long enough' line).
'Early stop' (途中停止) = no deliverable AND the last step has neither a tool call nor text."""
import sqlite3, json, os, sys, glob, re, gzip, shutil, tempfile
ES_VERSION = "es2"      # + 'announce' type (the model announces its next action in text and ends the response without a tool call); 'timeout' is no early stop; opencode.db.gz is read
INTENT = re.compile(r"(します|しましょう|ていきます|いきます|書きます|確認します|検証します|調べます|調査します|実行します|進めます|行います|直します|修正します|作成します|始めます|試します|見ます|読みます|開始します|取りかかります)[。.!！]?(?:[(（][^()（）]{0,40}[)）])?[。.!！\s]*$")
def open_db(d):
    p = os.path.join(d, "opencode.db")
    if os.path.exists(p): return sqlite3.connect("file:%s?mode=ro" % p, uri=True), None
    if not os.path.exists(p + ".gz"): return None, None
    t = tempfile.mktemp(suffix=".db")
    with gzip.open(p + ".gz") as f, open(t, "wb") as o: shutil.copyfileobj(f, o)
    return sqlite3.connect(t), t
CTX = 262144
def steps_1x(db):
    parts = {}
    for data, mid, t in db.execute("select data,message_id,time_created from part order by time_created,id"):
        p = json.loads(data); parts.setdefault(mid, []).append(p)
    out = []
    for mid, data in db.execute("select id,data from message order by time_created"):
        m = json.loads(data)
        if m.get("role") != "assistant": continue
        ps = parts.get(mid, []); tk = m.get("tokens") or {}; c = tk.get("cache") or {}
        out.append({"tool": any(p["type"] == "tool" for p in ps), "text": any(p["type"] == "text" and (p.get("text") or "").strip() for p in ps), "reasoning": sum(len(p.get("text", "")) for p in ps if p["type"] == "reasoning"),
                    "reason_tail": "".join(p.get("text", "") for p in ps if p["type"] == "reasoning")[-200:], "finish": m.get("finish"), "out": tk.get("output", 0), "ctx": (tk.get("input", 0) or 0) + (c.get("read", 0) or 0), "done": bool((m.get("time") or {}).get("completed")), "t": (m.get("time") or {}).get("completed")})
    return out, None
def steps_2x(db):
    out = []; comp = None
    for seq, typ, data in db.execute("select seq,type,data from session_message order by seq"):
        d = json.loads(data)
        if typ == "compaction": comp = {"seq": seq, "n_assistant_before": len(out), "time": (d.get("time") or {}).get("created")}
        if typ != "assistant": continue
        ct = d.get("content") or []; tk = d.get("tokens") or {}; c = tk.get("cache") or {}
        out.append({"tool": any(x.get("type") == "tool" for x in ct), "text": any(x.get("type") == "text" and (x.get("text") or "").strip() for x in ct), "reasoning": sum(len(x.get("text") or "") for x in ct if x.get("type") == "reasoning"),
                    "last_text": "".join(x.get("text") or "" for x in ct if x.get("type") == "text").strip()[-300:], "reason_tail": "".join(x.get("text") or "" for x in ct if x.get("type") == "reasoning")[-200:], "finish": d.get("finish"), "out": tk.get("output", 0), "ctx": (tk.get("input", 0) or 0) + (c.get("read", 0) or 0), "done": bool((d.get("time") or {}).get("completed")), "t": (d.get("time") or {}).get("completed")})
    return out, comp
def analyse(d, res=None):
    db, tmp = open_db(d)
    if db is None: return None
    tabs = {r[0] for r in db.execute("select name from sqlite_master")}
    S, comp = steps_2x(db) if ("session_message" in tabs and "message" not in tabs) else steps_1x(db)
    if not S: return None
    L = S[-1]; prev = S[-2] if len(S) > 1 else None
    if tmp:
        db.close(); os.unlink(tmp)
    kind = "tool" if L["tool"] else "text" if L["text"] else "reasoning-only" if L["reasoning"] else "empty"
    if res is None: res = json.load(open(os.path.join(d, "result.json"))) if os.path.exists(os.path.join(d, "result.json")) else {}
    deliv = bool((res.get("deliverable") or {}).get("found"))
    cond = res.get("conditions") or {}
    ctxs = [s["ctx"] for s in S]
    ps = lambda s: s and (s["finish"] == "length" or s["out"] >= 16000)
    pb = lambda s: s and "thought about this long enough" in s["reason_tail"]
    timed_out = bool(cond.get("timed_out")) or cond.get("opencode_exit") == 124 or bool(cond.get("watchdog"))
    # stop_type: the model ended its own response without a deliverable. reasoning-only/empty = the last step has no text and no tool call (thinking cut off, e.g. an end token in the middle of the thought);
    # announce = the last step is text only (finish=stop) and announces the next action ("...を検証します") without calling a tool; final-no-file = text-only end without an announcement (a normal-looking end, no file);
    # timeout = the trial was ended by the cap/watchdog (not the model's own stop)
    stop_type = None
    if not deliv:
        if timed_out: stop_type = "timeout"
        elif kind in ("reasoning-only", "empty"): stop_type = kind
        elif kind == "text" and L["finish"] == "stop": stop_type = "announce" if INTENT.search((L.get("last_text") or "").strip()) else "final-no-file"
    return {"trial": os.path.basename(d), "task": cond.get("task") or re.search(r"_(T\d)_", d).group(1), "harness": cond.get("harness"), "steps": len(S), "last_kind": kind, "last_finish": L["finish"], "last_completed": L["done"],
            "deliverable": deliv, "last_ctx": L["ctx"], "last_ctx_pct": round(100 * L["ctx"] / CTX, 1), "max_ctx": max(ctxs), "max_ctx_pct": round(100 * max(ctxs) / CTX, 1),
            "compaction": bool(comp), "compaction_before_last": (len(S) - comp["n_assistant_before"]) if comp else None, "prev_hit_output_cap": bool(ps(prev)), "prev_hit_think_budget": bool(pb(prev)), "last_hit_output_cap": bool(ps(L)), "last_hit_think_budget": bool(pb(L)),
            "early_stop": stop_type in ("reasoning-only", "empty", "announce"), "stop_type": stop_type, "early_stop_version": ES_VERSION, "last_text": (L.get("last_text") or "")[-200:], "opencode_exit": cond.get("opencode_exit"), "duration_min": round((cond.get("duration_sec") or 0) / 60, 1)}
if __name__ == "__main__":
    root, outmd = sys.argv[1], sys.argv[2]
    rows = []
    for d in sorted(glob.glob(os.path.join(root, "2026*"))):
        if any(k in d for k in ("smoke", "guardtest")): continue
        try: r = analyse(d)
        except Exception as e: r = None; print("ERR", d, e)
        if r: rows.append(r)
    if len(sys.argv) > 3: json.dump(rows, open(sys.argv[3], "w"), ensure_ascii=False, indent=1)
    L = ["| 試行 | 課題 | 版 | 最後の終わり方 | finish | 成果物 | 最後の入力トークン(使用率) | 最大(使用率) | 要約 | 直前が出力上限 | 直前が思考上限 | 途中停止 |", "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        L.append("| %s | %s | %s | %s | %s | %s | %d (%.1f%%) | %d (%.1f%%) | %s | %s | %s | %s |" % (r["trial"][:62], r["task"], r["harness"] or "?", r["last_kind"], r["last_finish"], "あり" if r["deliverable"] else "なし", r["last_ctx"], r["last_ctx_pct"], r["max_ctx"], r["max_ctx_pct"], "あり" if r["compaction"] else "-", "はい" if r["prev_hit_output_cap"] else "-", "はい" if r["prev_hit_think_budget"] else "-", "**はい**" if r["early_stop"] else "-"))
    open(outmd, "w").write("\n".join(L) + "\n"); print(len(rows), "trials;", sum(r["early_stop"] for r in rows), "early stops")
