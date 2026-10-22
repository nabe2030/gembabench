"""Condition guard: makes sure that trials which are meant to be compared really ran under the same conditions (for example, that one configuration did not
silently run with the server's default thinking while another sent reasoning_effort=medium / reasoning_budget_tokens=8192).
Run at the start of every trial (called from run_trial.py before anything touches a container or a model server):
  1. LOCK   -- the body's comparable fields (thinking request_extras, model_options, header/chunk/total timeouts, limit.output) must equal condition_lock.json.
               The lock is one reference for every configuration, so two of them cannot silently differ. Bodies listed under "exempt_bodies" (smoke) and --smoke runs skip it.
  2. PREVIOUS -- the whole body definition (minus apiKey) must equal the one recorded in conditions.json of the most recent earlier trial with the same label
               (a servers.json edit in the middle of a series is a drift).
  3. CROSS-LANE -- informational only: differences against the newest trial of the other lane, logged.
A detected difference makes run_trial.py stop (exit 5, abort.json) unless BENCH_ALLOW_COND_DIFF=<reason> is set (the reason is recorded in conditions.json).
A bug inside the guard itself never stops a trial (fail-open, WARN in runner.log); only a detected difference does."""
import glob, json, os

LOCK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "condition_lock.json")
LOCK_KEYS = ("request_extras", "model_options", "headerTimeout", "chunkTimeout", "timeout")

def signature(body):
    """Comparable part of a body definition; independent of which server/model it points at."""
    sig = {k: body.get(k) for k in LOCK_KEYS}
    sig["limit_output"] = (body.get("limit") or {}).get("output")
    return sig

def _strip(body):
    return {k: v for k, v in body.items() if k != "apiKey"}

def _recent_conditions(res_root, label, lane=None, exclude_lane=None, limit=1):
    """conditions.json of the newest finished trials: same label (lane=None) or newest of a given lane."""
    out = []
    for d in sorted(glob.glob(os.path.join(res_root, "2026*")), reverse=True):
        p = os.path.join(d, "conditions.json")
        if not os.path.exists(p) or "ABORTED" in os.path.basename(d): continue
        try: c = json.load(open(p))
        except Exception: continue
        if label is not None and c.get("model_label") != label: continue
        if lane is not None and c.get("lane", "a") != lane: continue
        if exclude_lane is not None and c.get("lane", "a") == exclude_lane: continue
        out.append(c)
        if len(out) >= limit: break
    return out

def _diff(a, b):
    return {k: (a.get(k), b.get(k)) for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)}

def check(body, body_key, label, smoke, res_root, lane, lock_path=LOCK_PATH):
    """Returns {"errors": [...], "info": [...]}."""
    errors, info = [], []
    try:
        lock = json.load(open(lock_path))
    except Exception as e:
        return {"errors": [], "info": ["WARN condition lock unreadable (%s): LOCK check skipped" % e]}
    # 1. lock
    if not smoke and body_key not in lock.get("exempt_bodies", []):
        want, have = lock["signature"], signature(body)
        for k, (w, h) in _diff(want, have).items():
            errors.append("LOCK: body '%s' %s = %s, but the lock requires %s" % (body_key, k, json.dumps(h, ensure_ascii=False), json.dumps(w, ensure_ascii=False)))
    else:
        info.append("LOCK skipped (%s)" % ("smoke run" if smoke else "exempt body"))
    # 2. previous trial with the same label
    prev = _recent_conditions(res_root, label)
    if prev:
        pb = _strip(prev[0].get("body") or {}); cb = _strip(body)
        for k, (p, c) in _diff(pb, cb).items():
            errors.append("PREVIOUS: body.%s changed within label '%s': previous trial %s -> now %s" % (k, label, json.dumps(p, ensure_ascii=False)[:80], json.dumps(c, ensure_ascii=False)[:80]))
    else:
        info.append("PREVIOUS: no earlier trial with label '%s' (first of the series)" % label)
    # 3. cross-lane (information)
    other = _recent_conditions(res_root, None, exclude_lane=lane)
    if other:
        ob = _strip(other[0].get("body") or {}); d = _diff(signature(ob), signature(body))
        info.append("CROSS-LANE vs lane %s newest trial (%s): %s" % (other[0].get("lane", "a"), other[0].get("trial_id", "?"), ("signature differs: " + json.dumps(d, ensure_ascii=False)[:300]) if d else "signature equal"))
    return {"errors": errors, "info": info}
