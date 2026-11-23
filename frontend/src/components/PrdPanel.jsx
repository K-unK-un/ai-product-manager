import { useState } from "react";
import { api } from "../api.js";

export default function PrdPanel({ prd, memory, projectId, streaming, onToast }) {
  const [tab, setTab] = useState("prd");
  return (
    <div className="prd-panel">
      <div className="prd-tabs">
        <button className={`prd-tab ${tab === "prd" ? "active" : ""}`} onClick={() => setTab("prd")}>
          📄 PRD 文档
        </button>
        <button className={`prd-tab ${tab === "memory" ? "active" : ""}`} onClick={() => setTab("memory")}>
          🧠 产品记忆{memory.length > 0 && <span className="tab-count">{memory.length}</span>}
        </button>
      </div>

      {tab === "prd" ? (
        <PrdView prd={prd} projectId={projectId} streaming={streaming} onToast={onToast} />
      ) : (
        <MemoryView memory={memory} />
      )}
    </div>
  );
}

function PrdView({ prd, projectId, streaming, onToast }) {
  const [exporting, setExporting] = useState(false);

  async function handleExport() {
    setExporting(true);
    try {
      await api.exportPrd(projectId);
      onToast?.("✅ PRD 已导出为 Markdown");
    } catch (e) {
      onToast?.(`❌ ${e.message || "导出失败"}`);
    } finally {
      setExporting(false);
    }
  }

  if (!prd) {
    return (
      <div className="prd-empty">
        <div className="prd-empty-icon">📄</div>
        <p>{streaming ? "正在生成 PRD…" : "还没有 PRD"}</p>
        <span>在左侧输入产品想法，上策会生成结构化 PRD 并展示在这里</span>
      </div>
    );
  }
  const ov = prd.overview || {};
  return (
    <div className="prd-doc">
      <div className="prd-head">
        <div>
          <div className="prd-title">{prd.title || "未命名产品"}</div>
          <div className="prd-subtitle">{ov.elevator_pitch || ""}</div>
        </div>
        {projectId && (
          <button
            className="btn-export"
            title="导出 Markdown"
            onClick={handleExport}
            disabled={exporting}
          >
            {exporting ? "导出中…" : "⬇ 导出"}
          </button>
        )}
      </div>

      {(prd.changelog || []).length > 0 && (
        <Section title="变更日志" icon="🕘" defaultOpen={false}>
          <ul className="changelog-list">
            {[...prd.changelog].reverse().map((c, i) => (
              <li key={i}>{c.note}</li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="产品概述" icon="🎯">
        <p className="prd-para">{ov.background}</p>
        <h4>产品目标</h4>
        <ul className="check-list">
          {ov.goals?.map((g, i) => <li key={i}>{g}</li>)}
        </ul>
        <h4>非目标</h4>
        <ul className="check-list muted-list">
          {ov.non_goals?.map((g, i) => <li key={i}>{g}</li>)}
        </ul>
      </Section>

      <Section title="目标用户" icon="👥">
        {prd.target_users?.map((u, i) => (
          <div key={i} className="user-card">
            <div className="user-card-name">{u.segment}</div>
            <p>{u.description}</p>
            <div className="kv"><span>需求</span>{u.needs?.join("；")}</div>
            <div className="kv"><span>痛点</span>{u.pain_points?.join("；")}</div>
          </div>
        ))}
      </Section>

      <Section title="用户故事" icon="📖">
        <table className="prd-table">
          <thead><tr><th>角色</th><th>需求</th><th>价值</th><th>优先级</th></tr></thead>
          <tbody>
            {prd.user_stories?.map((s, i) => (
              <tr key={i}>
                <td>{s.as_a}</td>
                <td>{s.want}</td>
                <td>{s.so_that}</td>
                <td><PriorityBadge p={s.priority} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="功能清单" icon="🧩">
        {prd.features?.map((f, i) => (
          <div key={i} className="feature-card">
            <div className="feature-name">
              {f.name} <PriorityBadge p={f.priority} />
            </div>
            <p>{f.description}</p>
            <div className="ac-list">
              {f.acceptance_criteria?.map((ac, j) => (
                <div key={j} className="ac-item">☐ {ac}</div>
              ))}
            </div>
          </div>
        ))}
      </Section>

      <Section title="竞品分析" icon="🥊">
        {!prd.competitor_analysis?.length && <p className="prd-para">暂无调研数据</p>}
        {prd.competitor_analysis?.map((c, i) => (
          <div key={i} className="comp-card">
            <div className="comp-name">{c.name} <span className="comp-pos">{c.positioning}</span></div>
            <div className="kv"><span>优势</span>{c.strengths?.join("；")}</div>
            <div className="kv"><span>劣势/机会</span>{c.weaknesses?.join("；")}</div>
            <div className="kv"><span>启发</span>{c.takeaway}</div>
          </div>
        ))}
      </Section>

      <Section title="数据指标" icon="📈">
        <table className="prd-table">
          <thead><tr><th>指标</th><th>定义</th><th>目标</th></tr></thead>
          <tbody>
            {prd.metrics?.map((m, i) => (
              <tr key={i}><td>{m.name}</td><td>{m.definition}</td><td>{m.target}</td></tr>
            ))}
          </tbody>
        </table>
      </Section>

      <Section title="里程碑" icon="🗓️">
        {prd.milestones?.map((m, i) => (
          <div key={i} className="milestone">
            <span className="milestone-dot" />
            <div>
              <div className="milestone-name">{m.phase} <span className="milestone-dur">{m.duration}</span></div>
              <div className="milestone-deliver">交付：{m.deliverables?.join("；")}</div>
            </div>
          </div>
        ))}
      </Section>

      <Section title="风险与应对" icon="⚠️">
        {prd.risks?.map((r, i) => (
          <div key={i} className="risk-row">
            <LevelBadge level={r.level} />
            <div>
              <div>{r.risk}</div>
              <div className="risk-mitigation">应对：{r.mitigation}</div>
            </div>
          </div>
        ))}
      </Section>

      <Section title="待确认问题" icon="❓">
        <ul className="check-list">
          {prd.open_questions?.map((q, i) => <li key={i}>{q}</li>)}
        </ul>
      </Section>
    </div>
  );
}

function MemoryView({ memory }) {
  const cats = {};
  for (const m of memory) (cats[m.category || "其他"] ||= []).push(m);
  if (memory.length === 0) {
    return (
      <div className="prd-empty">
        <div className="prd-empty-icon">🧠</div>
        <p>暂无产品记忆</p>
        <span>上策会在对话中自动沉淀产品关键事实（目标用户、商业模式、约束等），并在后续轮次中使用</span>
      </div>
    );
  }
  return (
    <div className="memory-view">
      {Object.entries(cats).map(([cat, facts]) => (
        <div key={cat} className="memory-group">
          <div className="memory-cat">{cat}</div>
          {facts.map((f, i) => (
            <div key={i} className="memory-fact">
              <div className="memory-key">{f.key}</div>
              <div className="memory-value">{f.value}</div>
              <div className="memory-time">{timeAgo(f.updated_at)}</div>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function Section({ title, icon, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="prd-section">
      <button className="prd-section-title" onClick={() => setOpen((v) => !v)}>
        <span>{icon} {title}</span>
        <span className="section-arrow">{open ? "▾" : "▸"}</span>
      </button>
      {open && <div className="prd-section-body">{children}</div>}
    </section>
  );
}

function PriorityBadge({ p }) {
  const cls = { P0: "p0", P1: "p1", P2: "p2" }[p] || "p2";
  return <span className={`badge-pri ${cls}`}>{p}</span>;
}

function LevelBadge({ level }) {
  const cls = { 高: "hi", 中: "mid", 低: "lo" }[level] || "lo";
  return <span className={`badge-level ${cls}`}>{level}</span>;
}

function timeAgo(iso) {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 3600) return `${Math.max(1, Math.floor(diff / 60))} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  return `${Math.floor(diff / 86400)} 天前`;
}
