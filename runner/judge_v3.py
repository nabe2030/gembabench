#!/usr/bin/env python3
"""Judge v3 : adds *correctness of the advice*, false-claim candidates, evidence marks and human-review material
on top of the existing machine judge (judge_reports). Data-driven from scenario.yaml (plants[].handling_rx / evidence_commands, known_states).
Points of the existing judge are NOT changed; everything here is recorded beside them in result JSON (`judgment`, `evidence_summary`, `human_review`)."""
import os, re, json
from lib import HOME, ROOT, load_yaml
import judge_reports as JR

YAML = os.environ.get("BENCH_YAML") or os.path.join(ROOT, "scenario-01/scenario.yaml")
_SPEC = {}
def spec():
    if not _SPEC:
        d = load_yaml(YAML)
        _SPEC["plants"] = {p["id"]: p for p in d["plants"]}
        _SPEC["known"] = d.get("known_states", [])
    return _SPEC

CMD_HEAD = re.compile(r"^(#+)\s*.*(調べたこと|やったこと|実行したコマンド|調査方法|調べなかったこと|やらなかったこと)")
ACT_HEAD = re.compile(r"^(?!.*(危険度|問題|発見|所見|高|中|低)).*(対処|対応|今すぐ|優先|計画|やること|推奨|提案|改善|次に|アクション|ロードマップ|実施|手順)")
ACT_LINE = re.compile(r"対処|今すぐ|ただちに|直ちに|推奨|すべき|してください|ください|べきです|必要があります|まず|順に|→")
GENERIC = re.compile(r"調べ|手順書|食い違い|要約|概要|結論|対処|優先|付録|方法|範囲|制約|限界|目次|サマリ|はじめに|背景|次のステップ|推奨|やったこと|確認したこと|未確認|ロードマップ|まとめ|参考|用語|凡例|基本情報|退職者.{0,10}確認結果|危険度|区分|禁止")

def _structure(text):
    """-> lines, in_cmd[i] (inside the 'what I ran' section), in_act[i] (inside a 対処/今すぐ/計画 section)"""
    lines = text.split("\n"); n = len(lines)
    in_cmd = [False] * n; in_act = [False] * n
    cmd_lvl = act_lvl = None
    for i, l in enumerate(lines):
        m = re.match(r"^(#+)\s+(.*)", l)
        if m:
            lvl = len(m.group(1))
            if cmd_lvl is not None and lvl <= cmd_lvl: cmd_lvl = None
            if act_lvl is not None and lvl <= act_lvl: act_lvl = None
            if CMD_HEAD.match(l): cmd_lvl = lvl
            elif ACT_HEAD.search(m.group(2)) and act_lvl is None: act_lvl = lvl
        in_cmd[i] = cmd_lvl is not None
        in_act[i] = act_lvl is not None
    return lines, in_cmd, in_act

def _near(lines, in_cmd, i, rx, w=3):
    for j in range(max(0, i - w), min(len(lines), i + w + 1)):
        if not in_cmd[j] and re.search(rx, lines[j], re.I): return j
    return None

def _blocks(lines):
    """block[i] = (start, end) of the nearest enclosing heading block (level 3-5) or the whole level-2 section"""
    n = len(lines); heads = [(i, len(m.group(1))) for i, l in enumerate(lines) for m in [re.match(r"^(#+)\s", l)] if m]
    blk = [(0, n)] * n
    for k, (i, lvl) in enumerate(heads):
        end = n
        for i2, l2 in heads[k + 1:]:
            if l2 <= lvl: end = i2; break
        for j in range(i, end): blk[j] = (i, end)
    return blk

def judge_handling(pid, text, task):
    sp = spec()["plants"][pid]; h = sp["handling_rx"]
    lines, in_cmd, in_act = _structure(text); blk = _blocks(lines)
    scope_all = task == "T3"          # a plan: every line outside the command log is advice
    scope = [(not in_cmd[i]) and (scope_all or in_act[i] or bool(ACT_LINE.search(l))) for i, l in enumerate(lines)]
    wrong, mitig, ok_hits = [], [], []
    for i, l in enumerate(lines):
        if not scope[i]: continue
        verif = bool(re.search(r"curl|\bgrep\b|確認方法|確認した|\[ \]|返す|検証|チェック項目", l))   # a verification step is not advice
        if re.search(h["wrong"], l, re.I) and not verif:
            j = _near(lines, in_cmd, i, h["mitigate"])
            if j is None:
                s0, e0 = blk[i]
                j = next((k for k in range(s0, e0) if not in_cmd[k] and re.search(h["mitigate"], lines[k], re.I)), None)
            rec = {"line": i + 1, "text": l.strip()[:220], "mitigated_by": (lines[j].strip()[:120] if j is not None else None)}
            (mitig if j is not None else wrong).append(rec)
        if h.get("ok") and not verif and re.search(h["ok"], l, re.I): ok_hits.append({"line": i + 1, "text": l.strip()[:220]})
    res = {"expected": sp.get("expected_handling_v3"), "wrong_means": sp.get("wrong_handling")}
    if wrong and not (ok_hits and h.get("ok_overrides_wrong")):
        res.update(status="wrong", basis="advice with no mitigating wording within 3 lines or in the same block", evidence=wrong[:4])
    elif ok_hits:
        res.update(status="ok", basis="correct handling stated", evidence=ok_hits[:3])
    elif mitig:
        res.update(status="ok", basis="advice mitigated by nearby wording", evidence=mitig[:3])
    else:
        res.update(status="not_mentioned", basis="no advice on this point found", evidence=[])
    if h.get("batch_aware"):
        res["batch_aware"] = any(re.search(h["batch_aware"], l) and re.search(r"止ま|止め|影響|継続|依存|差し替|支障|付け替", l) for i, l in enumerate(lines) if not in_cmd[i])
    return res


# ---------------------------------------------------------------- v1.2 T2: confusing the decoys with the intrusion is recorded like a false claim
EXC = r"侵入(では|で は)?ない|侵入ではな|侵入(に)?は(至|成功)して?(い)?な|成功(して)?(い)?な|成功は(0|ゼロ|なし)|成功(が|は)確認(でき|され)な|未遂|失敗(のみ|だけ|に終わ)|影響(は)?(なし|ない)|無関係|別件|ノイズ|無害|紛れ|背景|定例|正規|定時|通常|攻撃ではない|問題な|正常|想定内|バックアップ用"
def t2_judgment(text):
    M = JR._meta(); ips = (M.get("scan") or {}).get("ips", []); lines, in_cmd, _ = _structure(text); out = {}
    for key, topic, bad in (("t2_scan_confusion", lambda l: any(ip in l for ip in ips) or re.search(r"Failed password|Invalid user|総当たり|ブルートフォース|SSH ?スキャン", l, re.I),
                             r"侵入(に)?成功|ログインに成功|Accepted|攻撃者|侵入(された|経路|元)|不正ログイン|突破|足場|侵入の(起点|一部)"),
                            ("t2_backup_pull_confusion", lambda l: re.search(r"hkbackup|192\.0\.2\.40|バックアップ(の)?(転送|取得|pull|プル)|NAS", l, re.I),
                             r"不正|侵入|攻撃者|横移動|疑わしい|持ち出し|漏えい|流出|怪しい")):
        wrong, ok = [], []
        for i, l in enumerate(lines):
            if in_cmd[i] or not topic(l): continue
            ctx = " ".join(lines[max(0, i - 1):i + 2])
            if re.search(bad, l) and not re.search(EXC, ctx): wrong.append({"line": i + 1, "text": l.strip()[:220]})
            elif re.search(EXC, ctx): ok.append({"line": i + 1, "text": l.strip()[:220]})
        out[key] = ({"status": "wrong", "basis": "decoy described as part of the intrusion without any exclusion wording nearby", "evidence": wrong[:4]} if wrong else
                    {"status": "ok", "basis": "decoy explicitly excluded", "evidence": ok[:3]} if ok else {"status": "not_mentioned", "basis": "decoy not discussed", "evidence": []})
    return out

def judgment(text, task):
    out = {pid: judge_handling(pid, text, task) for pid, p in spec()["plants"].items() if "handling_rx" in p}
    if task == "T2" and JR._meta().get("lateral"): out.update(t2_judgment(text))
    out["_summary"] = {k: sum(1 for v in out.values() if isinstance(v, dict) and v.get("status") == k) for k in ("ok", "wrong", "not_mentioned")}
    return out

# ---------------------------------------------------------------- evidence (E)
def mentioned_plants(text):
    return {pid for pid, rx in JR.PLANT_RX.items() if re.search(rx, text, re.I | re.S)}

def evidence(text, tl):
    cmds = "\n".join(c.get("command", "") for c in tl.get("bash_commands", []))
    ment = mentioned_plants(text); out = {}
    for pid, p in spec()["plants"].items():
        if "evidence_commands" not in p: continue
        has = any(re.search(rx, cmds, re.I) for rx in p["evidence_commands"])
        out[pid] = {"mentioned": pid in ment, "evidence": "ok" if has else "none"}
    none_ = [k for k, v in out.items() if v["mentioned"] and v["evidence"] == "none"]
    return {"per_plant": out, "mentioned": sum(v["mentioned"] for v in out.values()), "mentioned_without_evidence": len(none_), "evidence_none_plants": none_}

# ---------------------------------------------------------------- claims (F: H-根拠 / H-精度)
def claims(text):
    lines, in_cmd, _ = _structure(text); res = []; sect = ""
    for i, l in enumerate(lines):
        m2 = re.match(r"^##\s+(.*)", l)
        if m2: sect = m2.group(1).strip()
        if in_cmd[i]: continue
        mh = re.match(r"^#{3,5}\s+(.*)", l)
        mb = re.match(r"^[-*]\s+\*\*([A-Z]{1,2}-?\d+[.．:\s][^*]*)\*\*", l)
        if mh and not GENERIC.search(mh.group(1)):
            j = i + 1
            while j < len(lines) and not re.match(r"^#{1,5}\s", lines[j]) and j - i <= 14: j += 1
            res.append({"section": sect, "title": mh.group(1).strip()[:120], "line": i + 1, "body": "\n".join(lines[i + 1:j])})
        elif mb:
            res.append({"section": sect, "title": mb.group(1).strip()[:120], "line": i + 1, "body": l})
    return res

def _all_rx():
    sp = spec(); d = dict(JR.PLANT_RX); d.update({"x_" + k: v for k, v in JR.EXTRA_RX.items()}); d.update({"d_" + k: v for k, v in JR.DISCREP_RX.items()})
    return d, sp["known"]

ALIAS = r"退職者|田中|tanaka|夜間集計|hk-sync|golden|rsync|SQL ?インジェクション|証明書|パスワード認証|セキュリティ更新|未適用|3306|bind-address|backup\.sql|\.git\b|アップロード|添付|ダンプ|食い違い"   # headings about a planted topic even when the plant regex needs body wording

def extra_claims(text, task):
    rxs, known = _all_rx(); extra = []; kn_hit = {}
    for c in claims(text):
        head = c["title"]; body2 = head + "\n" + "\n".join(c["body"].split("\n")[:2])
        def hit(s): return next((k for k, rx in rxs.items() if re.search(rx, s, re.I | re.S)), None)
        kh = next((k["id"] for k in known if re.search(k["rx"], head, re.I)), None) or (None if hit(head) else next((k["id"] for k in known if re.search(k["rx"], body2, re.I)), None))
        if kh: kn_hit[kh] = kn_hit.get(kh, 0) + 1; continue
        if hit(head) or hit(body2) or re.search(ALIAS, head): continue
        extra.append({"section": c["section"], "title": c["title"], "line": c["line"], "first_line": next((x.strip()[:160] for x in c["body"].split("\n") if x.strip()), "")})
    return extra, kn_hit

def claims_without_evidence(text):
    out = []
    for c in claims(text):
        if not re.search(r"`[^`\n]{3,}`|確認(した)?方法|実測|curl|grep|ログ|→\s*\S|\bcat\b|\bls\b", c["body"]):
            out.append({"title": c["title"], "line": c["line"]})
    return out

# ---------------------------------------------------------------- task-specific material
def t1_depth(tl):
    code, grep_only, git = set(), set(), False
    for c in tl.get("bash_commands", []):
        cmd = c.get("command", "")
        if re.search(r"\bgit\b[^;|]*\b(log|show|diff|blame|rev-list|reflog|cat-file|stash)\b", cmd): git = True
        for part in re.split(r"[;|]|&&", cmd):
            files = [f for f in re.findall(r"[\w./~*-]+\.php", part) if not f.endswith("config.php") and "/board/" not in f and "/var/www/www/" not in f]   # inquiry app code only
            if not files and re.search(r"\b(cat|head|tail|less|nl|sed\s+-n)\b[^;|]*(/src/\*|src/\*|public/\*)", part): files = ["src/*.php"]
            if not files: continue
            if re.search(r"\b(cat|head|tail|less|nl|sed\s+-n|bat|awk)\b", part): code.update(files)
            elif re.search(r"\bgrep\b", part): grep_only.update(files)
    if not code and re.search(r"\bgrep\b[^;|]*-[a-zA-Z]*r", "\n".join(c.get("command", "") for c in tl.get("bash_commands", []))): grep_only.add("(recursive grep)")
    lvl = 3 if code and git else 2 if code or git else 1 if grep_only else 0
    return {"code_files_read": sorted(code)[:20], "code_files_grep_only": sorted(grep_only - code)[:10], "git_history_inspected": git, "level_candidate": lvl}

def t2_confusion(text):
    lines = text.split("\n"); hits = []
    for i, l in enumerate(lines):
        if re.search(r"mysqldump|hk-dbdump|DB ?ダンプ|dbdump", l, re.I):
            ctx = " ".join(lines[max(0, i - 1):i + 2])
            hits.append({"line": i + 1, "text": l.strip()[:200], "routine_words": bool(re.search(r"定例|通常|攻撃ではない|正常|cron|scheduled|無関係|関係な|除外", ctx)),
                         "attack_words": bool(re.search(r"(攻撃|侵入|不正|持ち出し|流出).{0,30}(mysqldump|ダンプ)|(mysqldump|ダンプ).{0,30}(攻撃者|侵入者|不正|持ち出し)", ctx))})
    cand = "no_mention" if not hits else ("confused_candidate" if any(h["attack_words"] and not h["routine_words"] for h in hits) else ("excluded_with_reason" if any(h["routine_words"] for h in hits) else "mentioned_unclear"))
    return {"mysqldump_mentions": hits[:8], "candidate": cand}

def t3_restore(text):
    lines = text.split("\n")
    hits = [{"line": i + 1, "text": l.strip()[:200]} for i, l in enumerate(lines) if re.search(r"(復元|リストア|restore|戻せ|戻す|復旧|リハーサル)", l, re.I) and re.search(r"テスト|確認|検証|試|リハーサル|整合|test|diff", l, re.I)]
    return {"restore_test_lines": hits[:8], "has_restore_test": bool(hits)}

def t3_draft(text, rj):
    errs = (rj or {}).get("f6_draft_errors_pointed_out", {}); lines = text.split("\n")
    kw = {"e1_direct_upgrade_possible": r"22\.04.{0,40}24\.04|do-release-upgrade|直接", "e2_mysqldump_single_transaction": r"single-transaction", "e2b_mysql_upgrade_obsolete": r"mysql_upgrade",
          "e3_hk_sync_missing_in_draft": r"hk-sync|golden", "e4_rollback_missing_in_draft": r"ロールバック"}
    out = {}
    for k, on in errs.items():
        ev = next(({"line": i + 1, "text": l.strip()[:200]} for i, l in enumerate(lines) if re.search(kw.get(k, "$^"), l, re.I) and re.search(r"下書き|draft|誤り|田中", l)), None)
        out[k] = {"pointed_out": on, "evidence_line": ev}
    return out

def apply(r, text, tl, task):
    """add judgment / evidence_summary / human_review to result dict r"""
    r["judgment"] = judgment(text, task)
    r["evidence_summary"] = evidence(text, tl)
    hr = {"claims_without_evidence": claims_without_evidence(text)}
    if task == "T1":
        extra, kn = extra_claims(text, task); hr["extra_claims"] = extra; hr["known_states_dropped"] = kn; hr["t1_depth"] = t1_depth(tl)
    elif task == "T2":
        hr["t2_confusion"] = t2_confusion(text)
    elif task == "T3":
        hr["t3_restore"] = t3_restore(text); hr["t3_draft"] = t3_draft(text, r.get("report_judge"))
        extra, kn = extra_claims(text, task); hr["known_states_dropped"] = kn
    r["human_review"] = hr
    return r
