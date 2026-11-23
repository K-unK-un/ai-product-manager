"""工具函数：结构化 PRD → Markdown 导出。"""


def _md_list(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "（无）"


def prd_to_markdown(prd: dict, version: int) -> str:
    ov = prd.get("overview", {})
    lines = [
        f"# {prd.get('title', '产品需求文档')} — PRD",
        "",
        f"> 版本：v{version} ｜ 本文档由「上策 · AI 产品经理」自动生成，供团队评审使用",
        "",
    ]

    # 变更日志
    changelog = prd.get("changelog") or []
    if changelog:
        lines += ["## 变更日志", ""]
        lines += [f"- {c.get('note', '')}" for c in changelog]
        lines.append("")

    # 概述
    lines += [
        "## 一、产品概述",
        "",
        f"**一句话定位**：{ov.get('elevator_pitch', '')}",
        "",
        f"**背景**：{ov.get('background', '')}",
        "",
        "**产品目标**",
        _md_list(ov.get("goals", [])),
        "",
        "**非目标（暂不做）**",
        _md_list(ov.get("non_goals", [])),
        "",
    ]

    # 目标用户
    lines += ["## 二、目标用户", ""]
    for i, u in enumerate(prd.get("target_users", []), 1):
        lines += [
            f"### {i}. {u.get('segment', '')}",
            f"- 画像：{u.get('description', '')}",
            f"- 需求：{'；'.join(u.get('needs', []))}",
            f"- 痛点：{'；'.join(u.get('pain_points', []))}",
            "",
        ]

    # 用户故事
    lines += ["## 三、用户故事", "", "| 角色 | 需求 | 价值 | 优先级 |", "| --- | --- | --- | --- |"]
    for s in prd.get("user_stories", []):
        lines.append(f"| {s.get('as_a')} | {s.get('want')} | {s.get('so_that')} | {s.get('priority')} |")
    lines.append("")

    # 功能清单
    lines += ["## 四、功能清单", ""]
    for i, f in enumerate(prd.get("features", []), 1):
        lines.append(f"### 4.{i} {f.get('name')}（{f.get('priority')}）")
        lines.append(f"{f.get('description', '')}")
        lines.append("")
        lines.append("**验收标准**")
        lines += [f"- [ ] {ac}" for ac in f.get("acceptance_criteria", [])]
        lines.append("")

    # 竞品分析
    comps = prd.get("competitor_analysis") or []
    lines += ["## 五、竞品分析", ""]
    if not comps:
        lines += ["（暂无调研数据）", ""]
    for c in comps:
        lines += [
            f"### {c.get('name')}（{c.get('positioning', '')}）",
            f"- 优势：{'；'.join(c.get('strengths', []))}",
            f"- 劣势/机会：{'；'.join(c.get('weaknesses', []))}",
            f"- 启发：{c.get('takeaway', '')}",
            "",
        ]

    # 指标
    lines += ["## 六、数据指标", "", "| 指标 | 定义 | 目标 |", "| --- | --- | --- |"]
    for m in prd.get("metrics", []):
        lines.append(f"| {m.get('name')} | {m.get('definition')} | {m.get('target')} |")
    lines.append("")

    # 里程碑
    lines += ["## 七、里程碑", ""]
    for m in prd.get("milestones", []):
        lines.append(f"- **{m.get('phase')}**（{m.get('duration')}）：{'；'.join(m.get('deliverables', []))}")
    lines.append("")

    # 风险
    lines += ["## 八、风险与应对", "", "| 风险 | 等级 | 应对 |", "| --- | --- | --- |"]
    for r in prd.get("risks", []):
        lines.append(f"| {r.get('risk')} | {r.get('level')} | {r.get('mitigation')} |")
    lines.append("")

    # 待确认
    lines += ["## 九、待确认问题", ""]
    lines.append(_md_list(prd.get("open_questions", [])))
    lines.append("")

    return "\n".join(lines)
