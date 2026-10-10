#!/usr/bin/env python3
"""lhg-study-abroad 确定性文书审计：32 条规则，零第三方依赖。

扫描交付目录（ps-*.md 个人陈述、lor-*.md 推荐信、meta.json 元数据），
输出 JSON 与人类可读报告；有 blocker 时以 exit code 2 退出
（供 hooks 与 CI 使用）。

用法：
    python3 essay_audit.py --target <目录> [--format json|text] [--fail-on blocker|warning|nit]

规则文案均为本项目原创（方法论思路受各大学招生办官网公开写作建议的
高层启发，未复制任何第三方原文；详见仓库 ATTRIBUTION.md）。

诚实红线：脚本只做"机器可判定"的检查（结构完整性、陈词、字数、
占位符、推荐信比较级等），不判定"写得好不好"，更不编造申请人经历。
"""

import argparse
import json
import os
import re
import sys

VERSION = "1.0.0"
TOOL = "lhg-study-abroad/study-review"

SKIP_DIRS = {".git", "__pycache__", "node_modules", "dist", "build"}

# ---------------------------------------------------------------- 数据模型
class Finding:
    __slots__ = ("rule_id", "severity", "category", "title", "file", "line", "snippet", "detail")

    def __init__(self, rule_id, severity, category, title, file, line, snippet, detail):
        self.rule_id = rule_id
        self.severity = severity
        self.category = category
        self.title = title
        self.file = file
        self.line = line
        self.snippet = snippet
        self.detail = detail

    def to_dict(self):
        return {
            "rule_id": self.rule_id, "severity": self.severity,
            "category": self.category, "title": self.title,
            "file": self.file, "line": self.line,
            "snippet": self.snippet, "detail": self.detail,
        }


def read_text(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except UnicodeDecodeError:
        return None
    except OSError:
        return ""


def collect(target):
    ps, lors, metas = [], [], []
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            p = os.path.join(root, f)
            fl = f.lower()
            if fl.startswith("ps-") and fl.endswith(".md"):
                ps.append(p)
            elif fl.startswith("lor-") and fl.endswith(".md"):
                lors.append(p)
            elif fl == "meta.json":
                metas.append(p)
    return {"ps": sorted(ps), "lor": sorted(lors), "metas": sorted(metas)}


# ---------------------------------------------------------------- 规则注册表
RULES = []
_RULE_BY_ID = {}


def rule(rule_id, severity, category, title, detail):
    def deco(fn):
        r = {"id": rule_id, "severity": severity, "category": category,
             "title": title, "detail": detail}
        _RULE_BY_ID[rule_id] = r
        r["check"] = fn
        RULES.append(r)
        return fn
    return deco


def _mk(rule_id, path, line, snippet):
    r = _RULE_BY_ID[rule_id]
    return Finding(r["id"], r["severity"], r["category"], r["title"],
                   path, line, snippet[:160], r["detail"])


# ---------------------------------------------------------------- 自建表
# 陈词滥调（招生官视角的高频空话），持续扩充
CLICHES = [
    "从小就热爱", "从小我就对", "自幼便", "怀揣梦想", "梦想的种子",
    "扬帆起航", "追逐梦想", "梦寐以求", "耳濡目染", "人生的转折点",
    "受益匪浅", "刻骨铭心", "意义非凡", "孜孜不倦", "废寝忘食",
    "不是终点而是起点",
]
# 占位符：终稿里出现任何一个都是 blocker
PLACEHOLDERS = [
    r"\[.{0,20}(待填|填写|学校|姓名|专业|成绩).{0,20}\]",
    r"XXX+", r"待定", r"待填写", r"某大学", r"某某", r"\bTBD\b",
    r"\[insert",
]
# 绝对化成就表述：需要佐证，机器只能提醒
ABSOLUTE_CLAIMS = ["第一名", "冠军", "满分", "最高分", "全系第一", "全校第一",
                   "国家级一等奖", "唯一入选"]
# 反思/成长弧线关键词
REFLECT_WORDS = ["反思", "意识到", "让我明白", "让我懂得", "成长", "改变了我",
                 "从中学会", "领悟", "realiz", "reflect", "growth", "learned"]
# 动机关键词
MOTIVE_WORDS = ["为什么", "契机", "源于", "起因", "吸引我", "motivat", "why ",
                "inspir"]
# 未来规划关键词
FUTURE_WORDS = ["毕业后", "未来", "职业", "回国", "规划", "打算", "目标是",
                "career", "future", "plan to", "aspire"]
# 推荐信关系关键词
REL_WORDS = ["认识", "授课", "指导", "教过", "taught", "supervised", "known",
             "advisor", "instructed"]
# 比较级关键词
COMPAR_WORDS = ["同届", "前", "%", "top", "相比", "相较", "among", "compared",
                "最", "之一", "percentile", "rank"]
# 事例关键词
EXAMPLE_WORDS = ["例如", "比如", "记得有一次", "有一次", "当时", "for example",
                 "for instance", "once", "instance"]
# 空泛赞美词（无事例支撑时计入）
VAIN_WORDS = ["优秀", "出色", "卓越", "勤奋", "刻苦", "聪明", "极具天赋",
              "outstanding", "excellent", "exceptional", "diligent"]
# 联系方式
CONTACT_RE = re.compile(r"@|电话|tel|phone|邮箱|email|联系方式", re.I)
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
EN_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
NUM_RE = re.compile(r"\d+(?:\.\d+)?%?")


def count_words(text):
    """中英混合字数：CJK 字符逐字计，英文按词计。"""
    cjk = len(CJK_RE.findall(text))
    en = len(EN_WORD_RE.findall(text))
    return cjk + en


def paragraphs(text):
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def load_meta(files):
    meta = {}
    for p in files:
        try:
            with open(p, encoding="utf-8") as fh:
                meta.update(json.load(fh))
        except Exception:
            pass
    return meta


def _line_of(text, idx):
    return text.count("\n", 0, idx) + 1


# ---------------------------------------------------------------- 规则：PS 结构 STR-*
@rule("STR-PS-001", "warning", "结构", "PS 缺动机段",
      "个人陈述没有出现动机类表述（为什么/契机/源于/吸引我）。招生官想知道"
      "你为什么选这个方向，没有动机的 PS 读起来像简历复述。")
def _s1(ctx):
    out = []
    for p in ctx["ps"]:
        t = ctx["texts"][p]
        if not any(w in t for w in MOTIVE_WORDS):
            out.append(_mk("STR-PS-001", p, 1, t[:80]))
    return out


@rule("STR-PS-002", "warning", "结构", "PS 缺经历-反思-成长弧线",
      "全文没有反思/成长类表述（反思/意识到/让我明白/成长）。只讲经历不讲"
      "反思，是 PS 最常见的平庸形态：招生官要的是'这件事如何改变了你'。")
def _s2(ctx):
    out = []
    for p in ctx["ps"]:
        t = ctx["texts"][p]
        if not any(w in t for w in REFLECT_WORDS):
            out.append(_mk("STR-PS-002", p, 1, t[:80]))
    return out


@rule("STR-PS-003", "warning", "结构", "PS 缺 Why School",
      "全文未出现 meta.json 里声明的目标学校名。Why School 不能只写排名和"
      "地理位置，要写具体的人/课/实验室，否则招生官默认你是海投模板。")
def _s3(ctx):
    out = []
    school = (ctx["meta"].get("target_school") or "").strip()
    if not school:
        return out
    for p in ctx["ps"]:
        t = ctx["texts"][p]
        if school not in t:
            out.append(_mk("STR-PS-003", p, 1, "目标学校：%s" % school))
    return out


@rule("STR-PS-004", "warning", "结构", "PS 缺 Why Major",
      "全文未出现 meta.json 里声明的目标专业/项目名。Why Major 要回答"
      "'为什么是这个项目而不是隔壁学校同类项目'。")
def _s4(ctx):
    out = []
    major = (ctx["meta"].get("target_program") or "").strip()
    if not major:
        return out
    for p in ctx["ps"]:
        t = ctx["texts"][p]
        if major not in t:
            out.append(_mk("STR-PS-004", p, 1, "目标项目：%s" % major))
    return out


@rule("STR-PS-005", "warning", "结构", "PS 缺未来规划",
      "全文没有未来规划表述（毕业后/职业/规划）。招生官用未来规划判断你的"
      "目标是否清晰、与项目培养方向是否一致。")
def _s5(ctx):
    out = []
    for p in ctx["ps"]:
        t = ctx["texts"][p]
        if not any(w in t for w in FUTURE_WORDS):
            out.append(_mk("STR-PS-005", p, 1, t[:80]))
    return out


@rule("STR-PS-006", "nit", "结构", "PS 结尾过弱",
      "最后一段少于 30 字（词），可能虎头蛇尾。结尾建议回扣开头或点题，"
      "不要新开一个话题。")
def _s6(ctx):
    out = []
    for p in ctx["ps"]:
        paras = paragraphs(ctx["texts"][p])
        if paras and count_words(paras[-1]) < 30:
            out.append(_mk("STR-PS-006", p, _line_of(ctx["texts"][p],
                         ctx["texts"][p].rfind(paras[-1])), paras[-1][:80]))
    return out


# ---------------------------------------------------------------- 规则：推荐信结构 LOR-*
@rule("STR-LOR-001", "warning", "结构", "推荐信缺推荐关系声明",
      "全文未说明推荐人与申请人的关系（认识/授课/指导/认识时长）。"
      "没有关系声明的推荐信可信度打折。")
def _l1(ctx):
    out = []
    for p in ctx["lor"]:
        t = ctx["texts"][p]
        if not any(w in t for w in REL_WORDS):
            out.append(_mk("STR-LOR-001", p, 1, t[:80]))
    return out


@rule("STR-LOR-002", "warning", "结构", "推荐信缺联系方式",
      "全文未出现联系方式（邮箱/电话）。招生办可能核实推荐人身份，"
      "缺少联系方式会被视为不完整。")
def _l2(ctx):
    out = []
    for p in ctx["lor"]:
        t = ctx["texts"][p]
        if not CONTACT_RE.search(t):
            out.append(_mk("STR-LOR-002", p, 1, t[:80]))
    return out


@rule("LOR-EX-001", "warning", "推荐信", "推荐信缺具体事例",
      "全文没有事例标记（例如/比如/记得有一次/数字）。'他很优秀'式的推荐信"
      "等于没写：具体事例是推荐信唯一的货币。")
def _l3(ctx):
    out = []
    for p in ctx["lor"]:
        t = ctx["texts"][p]
        if not any(w in t for w in EXAMPLE_WORDS) and len(NUM_RE.findall(t)) < 2:
            out.append(_mk("LOR-EX-001", p, 1, t[:80]))
    return out


@rule("LOR-CMP-001", "warning", "推荐信", "推荐信缺比较级写法",
      "全文没有比较级表述（同届中/前 X%/top/相比）。招生官最想看到的是"
      "'他在我教过的学生里处于什么位置'，没有比较级就没有信息量。")
def _l4(ctx):
    out = []
    for p in ctx["lor"]:
        t = ctx["texts"][p]
        if not any(w in t for w in COMPAR_WORDS):
            out.append(_mk("LOR-CMP-001", p, 1, t[:80]))
    return out


@rule("LOR-GEN-001", "warning", "推荐信", "推荐信空泛赞美过多",
      "空泛赞美词（优秀/出色/卓越/勤奋…）出现 5 次以上且数字少于 2 个。"
      "赞美要有事例或数字托底，否则是正确的废话。")
def _l5(ctx):
    out = []
    for p in ctx["lor"]:
        t = ctx["texts"][p]
        vain = sum(t.count(w) for w in VAIN_WORDS)
        nums = len(NUM_RE.findall(t))
        if vain >= 5 and nums < 2:
            out.append(_mk("LOR-GEN-001", p, 1,
                            "空泛赞美 %d 次，数字 %d 个" % (vain, nums)))
    return out


# ---------------------------------------------------------------- 规则：陈词 CLC-*
def _cliche_rule(rid, words):
    @rule(rid, "warning", "陈词", "陈词滥调：%s" % " / ".join(words[:2]),
          "出现招生官高频空话（%s）。这类句子几乎每篇 PS 都有，出现即减分："
          "删掉或换成你自己的具体细节。" % "、".join(words))
    def _c(ctx):
        out = []
        for p in ctx["ps"] + ctx["lor"]:
            t = ctx["texts"][p]
            for w in words:
                i = t.find(w)
                if i >= 0:
                    out.append(_mk(rid, p, _line_of(t, i),
                                    t[max(0, i - 20):i + 30].replace("\n", " ")))
                    break
        return out
    return _c


_cliche_rule("CLC-001", ["从小就热爱", "从小我就对", "自幼便"])
_cliche_rule("CLC-002", ["怀揣梦想", "梦想的种子", "追逐梦想", "梦寐以求"])
_cliche_rule("CLC-003", ["扬帆起航", "人生的转折点"])
_cliche_rule("CLC-004", ["受益匪浅", "刻骨铭心", "意义非凡"])
_cliche_rule("CLC-005", ["孜孜不倦", "废寝忘食", "耳濡目染"])
_cliche_rule("CLC-006", ["不是终点而是起点"])


# ---------------------------------------------------------------- 规则：字数 LEN-*
@rule("LEN-PS-001", "blocker", "字数", "PS 超出字数上限",
      "字数超过 meta.json 声明的上限（默认 650）。超字数提交可能被系统截断，"
      "属于硬伤。")
def _n1(ctx):
    out = []
    limit = int(ctx["meta"].get("ps_word_limit") or 650)
    for p in ctx["ps"]:
        n = count_words(ctx["texts"][p])
        if n > limit:
            out.append(_mk("LEN-PS-001", p, 1, "字数 %d > 上限 %d" % (n, limit)))
    return out


@rule("LEN-PS-002", "warning", "字数", "PS 篇幅过短",
      "字数不足上限的 60%。篇幅过短通常意味着素材没挖透或结构缺段，"
      "先补内容再考虑精简。")
def _n2(ctx):
    out = []
    limit = int(ctx["meta"].get("ps_word_limit") or 650)
    for p in ctx["ps"]:
        n = count_words(ctx["texts"][p])
        if n < limit * 0.6:
            out.append(_mk("LEN-PS-002", p, 1, "字数 %d < 上限的 60%%" % n))
    return out


@rule("LEN-LOR-001", "warning", "字数", "推荐信过长",
      "推荐信超过 600 字（词）。推荐信宜精不宜长，超过一页纸招生官"
      "大概率跳读。")
def _n3(ctx):
    out = []
    for p in ctx["lor"]:
        n = count_words(ctx["texts"][p])
        if n > 600:
            out.append(_mk("LEN-LOR-001", p, 1, "字数 %d > 600" % n))
    return out


@rule("LEN-PARA-001", "nit", "字数", "存在超长段落",
      "单个段落超过 200 字（词）。超长段落在屏幕上是一堵墙，"
      "建议拆成 2~3 段。")
def _n4(ctx):
    out = []
    for p in ctx["ps"] + ctx["lor"]:
        t = ctx["texts"][p]
        for para in paragraphs(t):
            if count_words(para) > 200:
                i = t.find(para)
                out.append(_mk("LEN-PARA-001", p, _line_of(t, i),
                                "段落字数 %d" % count_words(para)))
                break
    return out


# ---------------------------------------------------------------- 规则：诚实 HON-*
@rule("HON-PH-001", "blocker", "诚实", "终稿含未填写的占位符",
      "发现占位符（[待填写]/XXX/某大学/某某/TBD 等）。带着占位符提交等于"
      "告诉招生官'我没写完'，必须填实或删掉。")
def _h1(ctx):
    out = []
    for p in ctx["ps"] + ctx["lor"]:
        t = ctx["texts"][p]
        for pat in PLACEHOLDERS:
            m = re.search(pat, t)
            if m:
                out.append(_mk("HON-PH-001", p, _line_of(t, m.start()),
                                t[max(0, m.start() - 20):m.end() + 20].replace("\n", " ")))
                break
    return out


@rule("HON-ABS-001", "warning", "诚实", "绝对化成就表述需佐证",
      "出现'第一名/冠军/满分'等绝对化表述。机器无法验证真假，请人工确认"
      "每一条都有成绩单/证书佐证；本插件绝不帮你编造，编了就是学术不端。")
def _h2(ctx):
    out = []
    for p in ctx["ps"] + ctx["lor"]:
        t = ctx["texts"][p]
        for w in ABSOLUTE_CLAIMS:
            i = t.find(w)
            if i >= 0:
                out.append(_mk("HON-ABS-001", p, _line_of(t, i),
                                t[max(0, i - 20):i + 20].replace("\n", " ")))
                break
    return out


@rule("HON-NUM-001", "warning", "诚实", "成绩数字请与官方记录核对",
      "文中出现 GPA/排名/分数类数字。请逐一核对与成绩单、语言成绩单一致；"
      "数字对不上是诚信问题，不是文笔问题。")
def _h3(ctx):
    out = []
    score_re = re.compile(r"(GPA|排名|托福|雅思|GRE|GMAT)\s*[:：]?\s*\d", re.I)
    for p in ctx["ps"] + ctx["lor"]:
        t = ctx["texts"][p]
        m = score_re.search(t)
        if m:
            out.append(_mk("HON-NUM-001", p, _line_of(t, m.start()),
                            t[max(0, m.start() - 10):m.end() + 20].replace("\n", " ")))
            break
    return out


# ---------------------------------------------------------------- 规则：招生官视角 ADM-*
@rule("ADM-SPEC-001", "warning", "招生官视角", "具体性不足：数字太少",
      "全文数字出现少于 3 个。具体数字（年份、人数、金额、排名、时长）是"
      "可信度的锚，没有数字的 PS 读起来像散文。")
def _a1(ctx):
    out = []
    for p in ctx["ps"]:
        t = ctx["texts"][p]
        nums = NUM_RE.findall(t)
        if len(nums) < 3:
            out.append(_mk("ADM-SPEC-001", p, 1, "数字仅 %d 个" % len(nums)))
    return out


@rule("ADM-FIT-001", "warning", "招生官视角", "项目匹配度证据不足",
      "meta.json 声明了目标教授/课程/实验室，但正文未出现。Why School "
      "写得越具体（点名教授、课程编号、实验室），越不像海投模板。")
def _a2(ctx):
    out = []
    fits = [x for x in (ctx["meta"].get("fit_keywords") or []) if x]
    if not fits:
        return out
    for p in ctx["ps"]:
        t = ctx["texts"][p]
        if not any(k in t for k in fits):
            out.append(_mk("ADM-FIT-001", p, 1,
                            "未提及：%s" % "、".join(fits[:3])))
    return out


@rule("ADM-REP-001", "nit", "招生官视角", "同一形容词重复过多",
      "某个形容词出现 6 次以上。重复用词暴露词汇量短板，用同义词或"
      "具体事例替换。")
def _a3(ctx):
    out = []
    adj = ["重要", "深刻", "巨大", "非常", "十分", "特别",
           "important", "significant", "very", "deeply"]
    for p in ctx["ps"] + ctx["lor"]:
        t = ctx["texts"][p]
        for w in adj:
            c = len(re.findall(re.escape(w), t, re.I)) if w.isascii() else t.count(w)
            if c >= 6:
                out.append(_mk("ADM-REP-001", p, 1, "“%s”出现 %d 次" % (w, c)))
                break
    return out


@rule("ADM-TONE-001", "nit", "招生官视角", "中英标点混用",
      "中文文书里出现英文半角标点（,.!?;:) 或英文文书里出现中文全角标点。"
      "标点不统一显得不专业，全文统一一遍。（邮箱、网址中的半角点已排除）")
def _a4(ctx):
    out = []
    for p in ctx["ps"] + ctx["lor"]:
        t = ctx["texts"][p]
        # 先剔除邮箱与网址，避免误伤
        t2 = re.sub(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", "", t)
        t2 = re.sub(r"https?://\S+|www\.\S+", "", t2)
        cjk_ratio = len(CJK_RE.findall(t2)) / max(1, len(t2))
        if cjk_ratio > 0.3:
            bad = re.findall(r"[,.!?;:]", t2)
            if bad:
                out.append(_mk("ADM-TONE-001", p, 1,
                                "中文文书含半角标点 %d 处" % len(bad)))
                break
        else:
            bad = re.findall(r"[，。！？；：]", t2)
            if bad:
                out.append(_mk("ADM-TONE-001", p, 1,
                                "英文文书含全角标点 %d 处" % len(bad)))
                break
    return out


# ---------------------------------------------------------------- 主流程
@rule("STR-META-001", "warning", "结构", "meta.json 缺失或关键字段缺失",
      "交付目录缺少 meta.json，或缺少 target_school/ps_word_limit 等字段。"
      "没有元数据，Why School/字数上限等规则只能跳过——不是'通过'，是'没查'。")
def _m0(ctx):
    out = []
    meta = ctx["meta"]
    missing = [k for k in ("target_school", "target_program", "ps_word_limit")
               if not meta.get(k)]
    if missing:
        out.append(_mk("STR-META-001", ctx["target"], 0,
                        "缺失字段：%s" % "、".join(missing)))
    return out


@rule("ADM-SINC-001", "warning", "招生官视角", "第一人称过少",
      "PS 里'我'出现少于 5 次。PS 是第一人称文书，'我'太少通常意味着"
      "在复述简历而不是讲自己的故事。")
def _a5(ctx):
    out = []
    for p in ctx["ps"]:
        t = ctx["texts"][p]
        c = t.count("我") + len(re.findall(r"\bI\b", t))
        if c < 5:
            out.append(_mk("ADM-SINC-001", p, 1, "第一人称仅 %d 次" % c))
    return out


@rule("STR-LOR-003", "nit", "结构", "推荐信缺落款",
      "全文未出现落款（签名/日期/职务）。正式推荐信应有推荐人签名、"
      "职务与日期。")
def _l6(ctx):
    out = []
    for p in ctx["lor"]:
        t = ctx["texts"][p]
        if not re.search(r"签名|日期|教授|副教授|讲师|博士|Sincerely|Professor|Ph\.?D", t):
            out.append(_mk("STR-LOR-003", p, 1, t[:80]))
    return out


_cliche_rule("CLC-007", ["座右铭", "人生格言"])


def run_audit(target, fail_on="blocker"):
    files = collect(target)
    texts = {}
    for p in files["ps"] + files["lor"]:
        t = read_text(p)
        texts[p] = t if t is not None else ""
    ctx = {"ps": files["ps"], "lor": files["lor"],
           "texts": texts, "meta": load_meta(files["metas"]),
           "target": target}
    findings = []
    for r in RULES:
        try:
            findings.extend(r["check"](ctx) or [])
        except Exception as e:
            findings.append(Finding(r["id"], "warning", r["category"],
                                    r["title"] + "（规则执行异常）",
                                    target, 0, "",
                                    "规则内部出错：%s（fail-open 记为 warning）" % e))
    sev_rank = {"blocker": 0, "warning": 1, "nit": 2}
    findings.sort(key=lambda f: (sev_rank.get(f.severity, 3), f.rule_id))
    counts = {"blocker": 0, "warning": 0, "nit": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    return {
        "tool": TOOL, "version": VERSION, "target": target,
        "summary": {"rules_run": len(RULES), "blocker": counts["blocker"],
                    "warning": counts["warning"], "nit": counts["nit"],
                    "total": len(findings),
                    "files": {"ps": len(files["ps"]), "lor": len(files["lor"])}},
        "findings": [f.to_dict() for f in findings],
    }, fail_on


def fmt_text(rep):
    s = rep["summary"]
    lines = ["[%s v%s] 目标：%s" % (rep["tool"], rep["version"], rep["target"]),
             "规则 %d 条 → blocker %d / warning %d / nit %d"
             % (s["rules_run"], s["blocker"], s["warning"], s["nit"]),
             "PS %d 篇，推荐信 %d 篇" % (s["files"]["ps"], s["files"]["lor"]), ""]
    for f in rep["findings"]:
        lines.append("[%s][%s] %s :: %s:%s" %
                     (f["severity"], f["rule_id"], f["title"], f["file"], f["line"]))
        if f["snippet"]:
            lines.append("    " + f["snippet"])
        lines.append("    " + f["detail"])
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="lhg-study-abroad 确定性文书审计")
    ap.add_argument("--target", required=True, help="交付目录")
    ap.add_argument("--format", choices=["json", "text"], default="text")
    ap.add_argument("--fail-on", choices=["blocker", "warning", "nit"],
                    default="blocker")
    args = ap.parse_args(argv)
    rep, fail_on = run_audit(args.target, args.fail_on)
    if args.format == "json":
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(fmt_text(rep))
    rank = {"blocker": 0, "warning": 1, "nit": 2}
    thresh = rank[fail_on]
    bad = any(rank.get(f["severity"], 3) <= thresh for f in rep["findings"])
    return 2 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
