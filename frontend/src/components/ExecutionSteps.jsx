import { useState } from "react";

const NODE_ICONS = {
  planner: "🧭",
  research: "🔎",
  research_summary: "📊",
  draft_prd: "✍️",
  review: "🛡️",
  update_memory: "🧠",
  finalize: "💬",
};

const NODE_TITLES = {
  planner: "任务规划",
  research: "信息检索",
  research_summary: "调研总结",
  draft_prd: "撰写 PRD",
  review: "质量自查",
  update_memory: "记忆更新",
  finalize: "生成回复",
};

// 任务计划与节点的对应关系（按计划长度区分意图路径）
const PLAN_NODE_MAP = {
  4: ["planner", "research_summary", "draft_prd", "review"],
  3: ["planner", "draft_prd", "review"],
  2: ["planner", "finalize"],
};

export default function ExecutionSteps({ steps, pending }) {
  const [open, setOpen] = useState(true);
  if (!steps || steps.length === 0) return null;

  const planner = steps.find((s) => s.kind === "node" && s.name === "planner");
  const plan = planner?.plan || planner?.detail?.plan || [];

  return (
    <div className="steps">
      <button className="steps-toggle" onClick={() => setOpen((v) => !v)}>
        <span>⚙️ Agent 执行过程</span>
        <span className="steps-toggle-arrow">{open ? "▲ 收起" : "▼ 展开"}</span>
      </button>
      {open && (
        <div className="steps-body">
          {plan.length > 0 && <PlanChecklist plan={plan} steps={steps} />}
          <div className="steps-timeline">
            {steps.map((s, i) => (
              <StepRow key={i} s={s} pending={pending} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function nodeStatus(name, steps) {
  const rows = steps.filter((s) => s.kind === "node" && s.name === name);
  if (rows.some((r) => r.status === "running")) return "running";
  if (rows.some((r) => r.status === "done")) return "done";
  return "pending";
}

function PlanChecklist({ plan, steps }) {
  const mapping = PLAN_NODE_MAP[plan.length] || [];
  return (
    <div className="plan-list">
      {plan.map((p, i) => {
        const mapped = mapping[i];
        let status = mapped ? nodeStatus(mapped, steps) : "pending";
        // 后续节点已完成而本节点未执行 → 视为跳过
        if (status === "pending" && mapping.slice(i + 1).some((n) => nodeStatus(n, steps) === "done")) {
          status = "skipped";
        }
        return (
          <div key={i} className={`plan-item ${status}`}>
            <span className="plan-icon">
              {status === "done" ? "✓" : status === "running" ? "◌" : status === "skipped" ? "—" : "·"}
            </span>
            <span className="plan-title">{p.title}</span>
            {p.detail && <span className="plan-detail">{p.detail}</span>}
          </div>
        );
      })}
    </div>
  );
}

function StepRow({ s, pending }) {
  const isNode = s.kind === "node";
  const detail = isNode ? s.detail || {} : {};
  const running = s.status === "running";
  const icon = isNode ? NODE_ICONS[s.name] || "•" : "🔧";
  const title = isNode ? s.title || NODE_TITLES[s.name] || s.name : s.name;

  const summary = isNode
    ? s.summary || (running ? "执行中…" : "")
    : s.input
      ? `输入：${Object.entries(s.input).map(([k, v]) => `${k}=${String(v).slice(0, 40)}`).join("，")}`
      : "";

  const detailRows = isNode
    ? nodeDetailRows(s, detail)
    : [{ label: "工具返回", value: s.summary || "", long: true }];

  return (
    <div className={`step-row ${running ? "running" : ""}`}>
      <div className="step-icon">{running ? "⏳" : icon}</div>
      <div className="step-content">
        <div className="step-title">
          {title}
          {isNode && s.name === "review" && detail.review && (
            <span className={`badge-review ${detail.review.passed ? "ok" : "fail"}`}>
              {detail.review.passed ? "✓" : "✗"} {detail.review.score} 分
            </span>
          )}
        </div>
        {summary && <div className="step-summary">{summary}</div>}
        {detailRows.map((r, i) => (
          <details key={i} className="step-details">
            <summary>{r.label}</summary>
            <pre>{r.value}</pre>
          </details>
        ))}
      </div>
    </div>
  );
}

function nodeDetailRows(s, detail) {
  const rows = [];
  if (s.name === "planner" && detail.analysis) {
    rows.push({ label: "需求分析", value: fmtAnalysis(detail.analysis) });
  }
  if (s.name === "research_summary" && detail.key_insights) {
    rows.push({ label: "关键洞察", value: detail.key_insights.join("\n") });
  }
  if (s.name === "draft_prd" && detail.changes?.length) {
    rows.push({ label: "修改点", value: detail.changes.join("\n") });
  }
  if (s.name === "review" && detail.review?.issues?.length) {
    rows.push({ label: "发现的问题", value: detail.review.issues.join("\n") });
  }
  if (s.name === "review" && detail.review?.suggestions?.length) {
    rows.push({ label: "改进建议", value: detail.review.suggestions.join("\n") });
  }
  if (s.name === "update_memory" && detail.updates?.length) {
    rows.push({
      label: "记忆更新",
      value: detail.updates.map((u) => `[${u.category}] ${u.key}：${u.value}`).join("\n"),
    });
  }
  return rows;
}

function fmtAnalysis(a) {
  if (!a) return "";
  const lines = [];
  if (a.summary) lines.push(`总结：${a.summary}`);
  if (a.goals?.length) lines.push(`目标：${a.goals.join("；")}`);
  if (a.target_users?.length) lines.push(`目标用户：${a.target_users.join("；")}`);
  if (a.scenarios?.length) lines.push(`场景：${a.scenarios.join("；")}`);
  return lines.join("\n");
}
