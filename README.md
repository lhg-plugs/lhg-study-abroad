<!-- About 简介（推送后填写到仓库 About 栏）：
留学文书专家：PS与推荐信的结构化写作 ｜ 一键安装：/plugin marketplace add lhg-plugs/lhg-study-abroad
-->
<!-- topics（推送后打）：claude-code, claude-plugin, agent-skills, study-abroad, application-essay -->

# lhg-study-abroad：留学文书专家

> **一句话介绍**：PS 与推荐信的结构化写作——背景素材梳理 → 文书结构搭建（Why School / Why Major / 经历-反思-成长弧线）→ 三轮改写 → 招生官视角自检，32 条确定性规则 5 秒出结果。
>
> **一键安装**：在 Claude Code 里运行
> ```
> /plugin marketplace add lhg-plugs/lhg-study-abroad
> /plugin install lhg-study-abroad@lhg-plugs
> ```

**诚实声明**：本插件绝不编造申请人的经历与成绩。所有数字、奖项、排名必须由你亲口确认；素材清单之外的"美化"要求会被明确拒绝。带着占位符的终稿会被硬门拦截，无法提交。

## 它是什么

`lhg-study-abroad` 是一个 Claude Code 插件（plugin 为主、skill 为辅），专为"DIY 留学申请、不想把文书完全外包"的人设计：

- **4 个命令**（小白入口）：`study-abroad` 背景素材输入（五维采集 + STAR 追问）→ `study-structure` 结构搭建（PS 五段式 / 推荐信四段式）→ `study-rewrite` 三轮改写（结构轮/语言轮/细节轮）→ `study-review` 招生官视角自检
- **4 个平台中立 skill**（方法论，可移植到豆包/Workbuddy 等 agent 平台）：背景素材梳理、文书结构搭建、多轮改写技法、招生官自检流程
- **3 个专家 agent**：背景素材教练、文书执笔、独立招生官评审
- **1 个硬门 hook**：写终稿（submit/final/定稿路径）前自动拦截未填占位符（可一键豁免，不骚扰）
- **32 条确定性自查规则**：文书结构完整性、陈词滥调扫描、字数限制、推荐信"具体事例+比较级"、招生官视角清单，纯 Python、零第三方依赖，5 秒出结果

工作流：`study-abroad`（采素材）→ `study-structure`（搭骨架）→ `study-rewrite`（改三遍）→ `study-review`（查一遍），也可以只用其中一段。

## 4 个命令用法

| 命令 | 作用 | 示例 |
|---|---|---|
| `/lhg-study-abroad:study-abroad` | 背景素材输入：五维采集 + STAR 追问 + 经历卡片 | `/lhg-study-abroad:study-abroad "大三，CS专业，想申美国硕士" --lang zh` |
| `/lhg-study-abroad:study-structure` | 结构搭建：PS 五段式 / 推荐信四段式大纲（用户拍板再写） | `/lhg-study-abroad:study-structure ./materials.md --type ps` |
| `/lhg-study-abroad:study-rewrite` | 三轮改写：结构轮→语言轮→细节轮，每轮只改一类问题 | `/lhg-study-abroad:study-rewrite ./outline.md --round 1` |
| `/lhg-study-abroad:study-review` | 招生官视角自检（脚本 + 人工评审清单） | `/lhg-study-abroad:study-review ./delivery/` |

## 自查说明

自查 = 确定性脚本（机器）+ 人工评审清单（人）：

1. 先跑 `scripts/audit/essay_audit.py`（32 条规则：结构 11、陈词 7、字数 4、诚实 3、招生官视角 7），零 AI 成本；
2. 发现分三级：**blocker**（必须修：占位符未填、PS 超字数，写终稿前 hook 会拦截占位符）、**warning**（修或写豁免理由）、**nit**（顺手修）；
3. 再按 `lhg-sa-audit` skill 的评审清单过一遍脚本抓不到的（30 秒测试、故事具体性、真诚度、项目匹配）。

blocker 清零才算做完；为清零改规则算作弊，不许。

## 目录结构

```
lhg-study-abroad/
├── .claude-plugin/          # plugin.json（插件清单）+ marketplace.json（本仓即市场）
├── commands/                # 4 个命令：study-abroad / study-structure / study-rewrite / study-review
├── skills/                  # 4 个平台中立 skill（素材梳理/结构搭建/改写技法/招生官自检）
├── agents/                  # 3 个专家 agent（material-coach / essay-writer / adcom-reviewer）
├── hooks/                   # 1 个硬门（终稿占位符拦截）+ 豁免说明
├── scripts/audit/           # 32 条确定性自查规则（零第三方依赖）
├── fixtures/                # 冒烟测试用例（坏/好对照）
├── smoke_test.py            # 一键冒烟测试
├── ATTRIBUTION.md           # 灵感来源与许可声明
└── LICENSE                  # MIT
```

## 什么时候用 / 什么时候不用（FAQ）

**什么时候用：**

- 你想 DIY 留学文书，不想把 PS 完全外包给中介时 → 用 `/lhg-study-abroad:study-abroad` 开始
- 你有一堆经历但不知道 PS 该讲哪几段时 → `study-structure` 帮你搭骨架、定主线
- 你的 PS 自己读着觉得"平淡、空"时 → `study-rewrite` 三轮改写，专治正确的废话
- 你要提交前怕翻车（占位符没填、超字数、Why School 像模板）时 → 跑 `/lhg-study-abroad:study-review`
- 你要请老师写推荐信，不知道给老师提供什么素材时 → 素材清单 + 推荐信四段式直接可用

**什么时候不用：**

- 你已签约留学中介全包服务（含文书）→ 中介的流程和本插件会打架，听中介的，别两边同时改
- 你申请的是纯研究型 PhD 且已有成熟的 SOP 模板 → 本插件的 PS 五段式偏授课型硕士，PhD 请用研究计划导向的结构
- 你希望 AI 替你"编"一段更漂亮的经历 → 本插件会明确拒绝，这是诚信红线，不是功能缺失

**风险点诚实说明：**

- **不替你做决定**：选校、选项目、文书主线，最终拍板都是你；插件只给结构和方法
- **审计规则是启发式**：32 条规则里的陈词表是自建常用表，会持续扩充但不可能穷尽；误报时按"误报处理"流程豁免，不要直接删规则
- **推荐信的比较级需要事实依据**：插件会要求你提供排名/比例依据，编不出来就不要写
- **英文 PS 的语言地道性**：插件保证结构与诚实，不保证英文母语级地道；终稿建议找英语好的朋友读一遍

## lhg-plugs 插件矩阵

| 插件 | 一句话 | 安装 |
|---|---|---|
| [lhg-video-edit](https://github.com/lhg-plugs/lhg-video-edit) | 一句话把口播素材剪成爆款短视频（+口播脚本子命令） | `/plugin install lhg-video-edit@lhg-plugs` |
| [lhg-fullstack](https://github.com/lhg-plugs/lhg-fullstack) | 小白一句话 → 高质量全栈应用 | `/plugin install lhg-fullstack@lhg-plugs` |
| [lhg-study-abroad](https://github.com/lhg-plugs/lhg-study-abroad) | 留学文书专家：PS 与推荐信的结构化写作 | `/plugin install lhg-study-abroad@lhg-plugs` |

## 自检与反馈

本插件自带质检：每次使用后可跑 `python3 smoke_test.py` 一键验证（JSON 合法、skill/command/agent 完整性、32 条规则、fixtures 命中、hooks 行为）。

发现 bug 或有改进建议，以 `[QC] <一句话问题>` 为标题提交到 https://github.com/lhg-plugs/lhg-study-abroad/issues，正文写清"复现步骤 → 实际表现 → 期望表现"。

## 出品：刘洪光

本插件由真人出镜 IP「刘洪光」（安徽合肥）出品，归属 [lhg-skills](https://github.com/lhg-skills)。

- GitHub 主页：https://github.com/lhg-skills —— 全部 skill 开源在此，欢迎 star
- 视频号：搜「刘洪光实名上网」
- 微信：lhgsmsw
