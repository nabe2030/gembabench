#!/usr/bin/env python3
"""Re-score the check items of a T4-T6 trial. The lane must be idle. Primary method: the trial's state_bundle (rescore_bundle.py). Items the bundle cannot decide (ok=None), or all items with --snapshot,
are scored from the end snapshot (endstate.py): the snapshot is restored, the nft rules are replayed, the live check runs, and the lane goes back to `clean`.
usage: rescore.py <trial dir> <tag> [--snapshot]   -> <trial dir>/check_items_rescored_<tag>.json (each item carries "source": bundle|snapshot); result.json is never touched.
Snapshots are not deleted here."""
import sys, os, json, time, subprocess
args = [x for x in sys.argv[1:] if not x.startswith("--")]; force_snap = "--snapshot" in sys.argv
d = os.path.abspath(args[0]); tag = args[1]
cond = json.load(open(os.path.join(d, "conditions.json"))); task = cond["task"]
os.environ["BENCH_LANE"] = cond.get("lane", "a"); os.environ.setdefault("BENCH_OC_MODE", "container")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib, checks, endstate, rescore_bundle as RB
from lib import sh, real, restore_clean
busy = subprocess.run("pgrep -f '^python3 run_(series|trial)\\.py'", shell=True, capture_output=True, text=True).stdout.strip()
if busy: sys.exit("a series/trial is running (pid %s); the lanes must be idle" % busy.split()[0])
base = checks.baseline()
items = []
if not force_snap:
    if not os.path.isdir(os.path.join(d, "state_bundle")): sys.exit("no state_bundle in this trial (use --snapshot if an end snapshot exists)")
    ok, _ = restore_clean()          # the db container must be up for the scratch-DB load of backup_restorable
    items = RB.score(task, d, base, RB.live_db_loader())
    for i in items: i["source"] = "bundle"
undec = [i["id"] for i in items if i["ok"] is None] if items else None
if force_snap or undec:
    rec = json.load(open(os.path.join(d, "end_snapshot.json"))) if os.path.exists(os.path.join(d, "end_snapshot.json")) else {}
    if not rec.get("created"):
        if force_snap: sys.exit("no end snapshot for this trial: %s" % json.dumps({k: rec.get(k) for k in ("skipped", "errors", "error")}))
        print("undecided items and no end snapshot to fall back to:", undec)
    else:
        W, D, S = real("web"), real("db"), rec["snapshot"]
        sh("incus stop %s %s --force 2>&1; incus snapshot restore %s %s && incus snapshot restore %s %s && incus start %s %s" % (W, D, W, S, D, S, D, W), 300)
        for _ in range(90):
            if lib.http_code("/") in ("200", "301", "302", "403", "404", "500") and lib.out("db", "mysql -N -e 'select 1' 2>/dev/null") == "1": break
            time.sleep(2)
        for c in lib.CONTAINERS:      # runtime-only state does not survive a snapshot: replay the firewall rules the model had loaded at the end
            f = os.path.join(d, "state_bundle", "nft_ruleset_%s.txt" % c)
            if os.path.exists(f) and open(f).read().strip():
                subprocess.run(lib.TESTENV + ["incus exec %s -- nft -f -" % real(c)], input="flush ruleset\n" + open(f).read(), text=True, capture_output=True); print("replayed nft ruleset in", c)
        time.sleep(3)
        try: live = checks.CHECKS[task]()
        finally: ok, secs = restore_clean(); print("restore_clean", ok, secs)
        for i in live: i["source"] = "snapshot"
        if force_snap: items = live
        else: items = [next((l for l in live if l["id"] == i["id"]), i) if i["ok"] is None else i for i in items]
else:
    restore_clean()
old = {i["id"]: i for i in (json.load(open(os.path.join(d, "result.json"))).get("check_items") or [])}
cmp_ = [{"id": i["id"], "old": old.get(i["id"], {}).get("ok"), "new": i["ok"], "weight": i["weight"], "source": i.get("source")} for i in items]
pts = lambda L: sum(i["weight"] for i in L if i["ok"])
json.dump({"tag": tag, "items": items, "compare": cmp_, "points_new": pts(items), "points_old": pts(old.values()), "undecided_in_bundle": undec},
          open(os.path.join(d, "check_items_rescored_%s.json" % tag), "w"), ensure_ascii=False, indent=1)
print("rescored", task, "new/old points:", pts(items), pts(old.values()), "differences:", [c for c in cmp_ if c["old"] != c["new"]])
