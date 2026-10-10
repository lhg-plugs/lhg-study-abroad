#!/usr/bin/env python3
"""lhg-study-abroad 硬门：写终稿前拦截未填占位符。

触发：PreToolUse / Write、Edit。脚本先判断本次写入的文件路径是否像
"待提交终稿"（路径含 submit / final / delivery / 定稿 / 终稿，大小写不敏感），
不是则 0 开销直接放行；是则扫描文件内容中的占位符
（[待填写]/XXX/某大学/某某/TBD 等）。

逃生方式（按推荐度排序）：
  1. 把占位符填实后再写终稿（推荐）。
  2. 紧急情况：LHG_SA_HOOKS_OFF=1（单次豁免本次 hook）。
  3. /plugin disable lhg-study-abroad（整个插件停用，hooks 不再触发）。

设计原则：脚本内部出错（读不到文件、解析失败等）时 fail-open 直接放行，
不因插件自身故障骚扰用户；真正的门禁在 /lhg-study-abroad:study-review。
零第三方依赖。
"""

import json
import os
import re
import sys

SUBMIT_RE = re.compile(r"submit|final|deliver|定稿|终稿", re.I)

PLACEHOLDER_RES = [
    re.compile(r"\[.{0,20}(待填|填写|学校|姓名|专业|成绩).{0,20}\]"),
    re.compile(r"XXX+"),
    re.compile(r"待定|待填写|某大学|某某|\bTBD\b"),
    re.compile(r"\[insert", re.I),
]


def find_placeholders(text):
    """返回 [(行号, 片段)]。"""
    hits = []
    for pat in PLACEHOLDER_RES:
        for m in pat.finditer(text):
            lineno = text.count("\n", 0, m.start()) + 1
            frag = text[max(0, m.start() - 24):m.end() + 24].replace("\n", " ")
            hits.append((lineno, frag))
            if len(hits) >= 10:
                return hits
    return hits


def main() -> int:
    # 逃生开关
    if os.environ.get("LHG_SA_HOOKS_OFF") == "1":
        return 0

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0  # 输入解析失败：fail-open

    tool_input = payload.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path", "") or ""

    # 非终稿路径：快速放行
    if not file_path or not SUBMIT_RE.search(file_path):
        return 0

    try:
        with open(file_path, encoding="utf-8") as fh:
            text = fh.read()
    except Exception:
        return 0  # 文件读不到（可能是新建）：fail-open

    try:
        hits = find_placeholders(text)
    except Exception:
        return 0  # 扫描自身出错：fail-open

    if not hits:
        return 0

    lines = [
        "终稿被 lhg-study-abroad 硬门拦截：发现 %d 处未填占位符，填实后再提交。"
        % len(hits),
        "文件：%s" % file_path,
        "",
    ]
    for lineno, frag in hits:
        lines.append("第 %d 行：…%s…" % (lineno, frag))
    lines += [
        "",
        "修复方式：把 [待填写]/XXX/某大学 等占位符填实；",
        "紧急豁免（单次）：LHG_SA_HOOKS_OFF=1",
        "注意：本插件绝不编造申请人经历与成绩，占位符只能由你本人填实。",
    ]
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "\n".join(lines),
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
