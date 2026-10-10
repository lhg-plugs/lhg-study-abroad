#!/usr/bin/env python3
"""lhg-study-abroad 插件冒烟测试：全部绿才算过。

检查项：
 1. 三个 JSON 合法（plugin.json / marketplace.json / hooks.json）
 2. 4 个 SKILL.md 都有 name/description frontmatter，且 150~400 行
 3. 4 个 commands 都有 description + argument-hint frontmatter
 4. 3 个 agents 都有 name/description/tools/model frontmatter
 5. skills 平台中立：不含 Claude Code 专有工具名
 6. fixtures：坏 fixture 的埋点规则必须全部命中且脚本 exit!=0；
    好 fixture 零 blocker 且 exit==0；
    LEN-PS-002（过短）与 STR-META-001（缺 meta）用临时目录单独覆盖
 7. hooks 脚本：非终稿路径放行 / 终稿+占位符拦截 / 逃生开关 / 读不到文件放行

用法：python3 smoke_test.py [--repo <插件根目录>]
退出码：0=全绿，1=有失败。
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((PASS if cond else FAIL, name, detail))
    return cond


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def frontmatter(path):
    """解析 markdown 顶部 --- YAML 块（只取一层 key: value）。"""
    text = read(path)
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    fm = {}
    for ln in text[3:end].split("\n"):
        m = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$", ln)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fm


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120, **kw)


# 预期的埋点命中（坏 fixture 必须全部命中）
BAD_MUST = {
    "STR-PS-001", "STR-PS-002", "STR-PS-003", "STR-PS-004", "STR-PS-005",
    "STR-PS-006",
    "STR-LOR-001", "STR-LOR-002", "STR-LOR-003",
    "LOR-EX-001", "LOR-CMP-001", "LOR-GEN-001",
    "CLC-001", "CLC-002", "CLC-003", "CLC-004", "CLC-005", "CLC-006", "CLC-007",
    "LEN-PS-001", "LEN-LOR-001",
    "HON-PH-001", "HON-ABS-001", "HON-NUM-001",
    "ADM-SPEC-001", "ADM-FIT-001", "ADM-REP-001", "ADM-TONE-001",
    "ADM-SINC-001",
}
# 平台中立红线：skill 正文不许出现这些 Claude Code 专有表述
NEUTRAL_DENY = ["Task tool", "Bash tool", "Edit tool", "Write tool", "Read tool",
                "AskUserQuestion", "subagent_type", "PreToolUse", "PostToolUse",
                "${CLAUDE_", "CLAUDE_PLUGIN_ROOT", "CLAUDE_PROJECT_DIR"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.path.dirname(os.path.abspath(__file__)))
    args = ap.parse_args()
    repo = os.path.abspath(args.repo)
    AUDIT = os.path.join(repo, "scripts", "audit")

    # 1. JSON 合法
    for rel in [".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
                "hooks/hooks.json"]:
        p = os.path.join(repo, rel)
        try:
            d = json.loads(read(p))
            check("JSON 合法: " + rel, True)
            if rel.endswith("plugin.json"):
                check("plugin.json name==lhg-study-abroad",
                      d.get("name") == "lhg-study-abroad", str(d.get("name")))
                check("plugin.json 有 version/description/author",
                      all(d.get(k) for k in ("version", "description", "author")))
            if rel.endswith("marketplace.json"):
                ps = d.get("plugins", [])
                check("marketplace.json source==./",
                      len(ps) == 1 and ps[0].get("source") == "./" and
                      ps[0].get("name") == "lhg-study-abroad", str(ps))
            if rel.endswith("hooks.json"):
                check("hooks.json 顶层有 hooks 包装", "hooks" in d)
                evts = d["hooks"]
                check("hooks.json 有 PreToolUse", "PreToolUse" in evts, str(list(evts)))
        except Exception as e:
            check("JSON 合法: " + rel, False, str(e))

    # 2. SKILL.md frontmatter + 行数
    for skill in ["lhg-sa-material", "lhg-sa-structure", "lhg-sa-essay",
                  "lhg-sa-audit"]:
        p = os.path.join(repo, "skills", skill, "SKILL.md")
        fm = frontmatter(p)
        check("skill frontmatter: " + skill,
              bool(fm.get("name")) and bool(fm.get("description")),
              "name=%s" % fm.get("name"))
        nlines = len(read(p).split("\n"))
        check("skill 行数 150~400: %s (%d 行)" % (skill, nlines),
              150 <= nlines <= 400, str(nlines))
        body = read(p)
        bad_words = [w for w in NEUTRAL_DENY if w in body]
        check("skill 平台中立: " + skill, not bad_words, "命中: %s" % bad_words)
        check("skill 有出品区: " + skill,
              "出品：刘洪光" in body and "https://github.com/lhg-skills" in body)
        check("skill 有自检与反馈: " + skill, "自检与反馈" in body)

    # 3. commands
    for cmd in ["study-abroad", "study-structure", "study-rewrite", "study-review"]:
        p = os.path.join(repo, "commands", cmd + ".md")
        fm = frontmatter(p)
        check("command description: " + cmd, bool(fm.get("description")),
              str(fm.get("description"))[:60])
        check("command argument-hint: " + cmd, bool(fm.get("argument-hint")),
              str(fm.get("argument-hint"))[:40])

    # 4. agents
    for ag in ["material-coach", "essay-writer", "adcom-reviewer"]:
        p = os.path.join(repo, "agents", ag + ".md")
        fm = frontmatter(p)
        check("agent frontmatter: " + ag,
              all(fm.get(k) for k in ("name", "description", "tools", "model")),
              str({k: fm.get(k) for k in ("name", "model")}))

    # 5. 审计脚本冒烟
    def audit_hits(target):
        r = run([sys.executable, os.path.join(AUDIT, "essay_audit.py"),
                 "--target", os.path.join(repo, target), "--format", "json"])
        try:
            d = json.loads(r.stdout)
        except Exception:
            return None, r.returncode, []
        return d["summary"], r.returncode, [f["rule_id"] for f in d["findings"]]

    s, code, ids = audit_hits("fixtures/bad")
    check("坏 fixture exit!=0", code != 0, "exit=%d" % code)
    check("坏 fixture blocker>0", s and s["blocker"] > 0, str(s))
    missing = BAD_MUST - set(ids)
    check("坏 fixture 埋点全命中 (%d/%d)" % (len(BAD_MUST - missing), len(BAD_MUST)),
          not missing, "缺失: %s" % sorted(missing))

    s, code, ids = audit_hits("fixtures/good")
    check("好 fixture 零 blocker", s and s["blocker"] == 0, str(s))
    check("好 fixture exit==0", code == 0, "exit=%d" % code)

    # LEN-PS-002 单独覆盖：临时写一个过短的 PS
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "ps-short.md"), "w") as fh:
            fh.write("太短了。\n")
        with open(os.path.join(td, "meta.json"), "w") as fh:
            fh.write('{"ps_word_limit": 650}')
        s, code, ids = audit_hits(td)
        check("LEN-PS-002 命中过短 PS", "LEN-PS-002" in ids, str(ids))

    # STR-META-001 单独覆盖：无 meta.json 的目录
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "ps-x.md"), "w") as fh:
            fh.write("随便写点内容。\n")
        s, code, ids = audit_hits(td)
        check("STR-META-001 命中缺 meta", "STR-META-001" in ids, str(ids))

    # 规则总数（对外口径：30+ 条）
    n = json.loads(run([sys.executable, os.path.join(AUDIT, "essay_audit.py"),
                        "--target", os.path.join(repo, "fixtures/good"),
                        "--format", "json"]).stdout)["summary"]["rules_run"]
    check("规则总数>=30 (%d)" % n, n >= 30, str(n))

    # 6. hooks 脚本
    def hook(script, payload, env=None):
        e = dict(os.environ); e.update(env or {})
        return run([sys.executable, os.path.join(repo, "hooks", script)],
                   input=payload, env=e)

    r = hook("check_placeholders_before_submit.py",
             '{"tool_input":{"file_path":"/tmp/notes/draft.md"}}')
    check("hook: 非终稿路径放行", r.returncode == 0 and not r.stdout.strip(),
          r.stdout[:80])

    with tempfile.TemporaryDirectory() as td:
        sub = os.path.join(td, "submit")
        os.makedirs(sub)
        bad_p = os.path.join(sub, "ps-final.md")
        with open(bad_p, "w") as fh:
            fh.write("正文……[待填写学校]……XXX\n")
        r = hook("check_placeholders_before_submit.py",
                 json.dumps({"tool_input": {"file_path": bad_p}}))
        try:
            d = json.loads(r.stdout)
            denied = d["hookSpecificOutput"]["permissionDecision"] == "deny"
        except Exception:
            denied = False
        check("hook: 终稿+占位符拦截", denied, r.stdout[:120])

        good_p = os.path.join(sub, "ps-final.md")
        with open(good_p, "w") as fh:
            fh.write("正文已填实，无占位符。\n")
        r = hook("check_placeholders_before_submit.py",
                 json.dumps({"tool_input": {"file_path": good_p}}))
        check("hook: 终稿+干净放行", r.returncode == 0 and not r.stdout.strip(),
              r.stdout[:80])

        with open(bad_p, "w") as fh:
            fh.write("正文……[待填写学校]\n")
        r = hook("check_placeholders_before_submit.py",
                 json.dumps({"tool_input": {"file_path": bad_p}}),
                 {"LHG_SA_HOOKS_OFF": "1"})
        check("hook: 逃生开关生效", r.returncode == 0 and not r.stdout.strip())

    # 读不到文件：fail-open
    r = hook("check_placeholders_before_submit.py",
             '{"tool_input":{"file_path":"/tmp/submit/不存在的文件.md"}}')
    check("hook: 读不到文件放行", r.returncode == 0 and not r.stdout.strip())

    # 报告
    print("=" * 60)
    print("lhg-study-abroad 冒烟测试报告")
    print("=" * 60)
    fails = 0
    for st, name, detail in results:
        mark = "✓" if st == PASS else "✗"
        print("%s %s %s" % (mark, st, name))
        if detail and st == FAIL:
            print("    → %s" % detail)
        if st == FAIL:
            fails += 1
    print("=" * 60)
    print("共 %d 项，通过 %d，失败 %d" % (len(results), len(results) - fails, fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
