import { useCallback, useEffect, useRef, useState } from "react";
import { api, getToken, setOnUnauthorized, setToken } from "./api.js";
import Sidebar from "./components/Sidebar.jsx";
import ChatArea from "./components/ChatArea.jsx";
import PrdPanel from "./components/PrdPanel.jsx";
import AuthScreen from "./components/AuthScreen.jsx";
import SettingsModal from "./components/SettingsModal.jsx";

export default function App() {
  const [auth, setAuth] = useState(() =>
    getToken() ? { username: localStorage.getItem("shangce_username") || "" } : null
  );
  const [projects, setProjects] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [detail, setDetail] = useState(null); // {project, messages, memory, prd}
  const [liveTurn, setLiveTurn] = useState(null); // 流式过程中的临时消息 {input, reply, steps}
  const [livePrd, setLivePrd] = useState(null); // 流式过程中实时更新的 PRD
  const [streaming, setStreaming] = useState(false);
  const [demoMode, setDemoMode] = useState(null);
  const [panelOpen, setPanelOpen] = useState(true);
  const [error, setError] = useState(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [toast, setToast] = useState(null);
  const toastTimer = useRef(null);
  const detailRef = useRef(null);
  detailRef.current = detail;

  const showToast = useCallback((text) => {
    setToast(text);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 3000);
  }, []);

  // 401 时退回登录页
  useEffect(() => {
    setOnUnauthorized(() => {
      setAuth(null);
      setActiveId(null);
      setDetail(null);
      setLiveTurn(null);
    });
  }, []);

  const handleLogout = useCallback(() => {
    setToken("");
    setAuth(null);
    setProjects([]);
    setActiveId(null);
    setDetail(null);
    setLiveTurn(null);
  }, []);

  const refreshProjects = useCallback(async () => {
    try {
      const data = await api.listProjects();
      setProjects(data.projects);
    } catch {}
  }, []);

  const refreshDetail = useCallback(async (id) => {
    if (!id) return;
    try {
      const data = await api.getProject(id);
      setDetail(data);
      setLivePrd(null);
    } catch {}
  }, []);

  const handleAuthed = useCallback(
    (a) => {
      localStorage.setItem("shangce_username", a.username);
      setAuth(a);
      setProjects([]);
      setActiveId(null);
      setDetail(null);
      refreshProjects();
    },
    [refreshProjects]
  );

  useEffect(() => {
    refreshProjects();
    api.health()
      .then((h) => setDemoMode(h.demo_mode))
      .catch(() => {});
  }, [refreshProjects]);

  const selectProject = useCallback(
    (id) => {
      if (streaming) return;
      setActiveId(id);
      setDetail(null);
      setLivePrd(null);
      setError(null);
      refreshDetail(id);
    },
    [streaming, refreshDetail]
  );

  const newProject = useCallback(() => {
    if (streaming) return;
    setActiveId(null);
    setDetail(null);
    setLivePrd(null);
    setError(null);
  }, [streaming]);

  const handleDelete = useCallback(
    async (id) => {
      await api.deleteProject(id);
      if (id === activeId) {
        setActiveId(null);
        setDetail(null);
        setLivePrd(null);
      }
      refreshProjects();
    },
    [activeId, refreshProjects]
  );

  const onEvent = useCallback((evt) => {
    switch (evt.type) {
      case "project": {
        setActiveId(evt.project.id);
        setDemoMode(evt.project.demo_mode);
        refreshProjects();
        break;
      }
      case "node": {
        setLiveTurn((prev) => {
          if (!prev) return prev;
          const steps = [...prev.steps];
          const idx = steps.findIndex(
            (s) => s.kind === "node" && s.name === evt.name && s.status === "running"
          );
          if (evt.status === "running") {
            if (idx >= 0) steps[idx] = { ...steps[idx], ...evt };
            else steps.push({ kind: "node", ...evt });
          } else {
            const row = { kind: "node", ...evt, detail: {} };
            for (const k of ["intent", "plan", "analysis", "summary", "competitor_count",
                             "key_insights", "prd", "changes", "review", "updates"]) {
              if (evt[k] !== undefined) row.detail[k] = evt[k];
            }
            row.summary = nodeSummary(evt);
            if (idx >= 0) steps[idx] = row;
            else steps.push(row);
            if (evt.name === "draft_prd" && evt.prd) setLivePrd(evt.prd);
          }
          const reply =
            evt.name === "finalize" && evt.status === "done" && evt.text
              ? evt.text
              : prev.reply;
          return { ...prev, steps, reply };
        });
        break;
      }
      case "tool": {
        setLiveTurn((prev) => {
          if (!prev) return prev;
          const steps = [...prev.steps];
          const idx = steps.findIndex(
            (s) => s.kind === "tool" && s.name === evt.name && s.status === "running"
          );
          if (evt.status === "running") {
            if (idx >= 0) steps[idx] = { ...steps[idx], ...evt };
            else steps.push({ kind: "tool", ...evt });
          } else {
            const row = { kind: "tool", ...evt, summary: evt.output || "" };
            if (idx >= 0) steps[idx] = row;
            else steps.push(row);
          }
          return { ...prev, steps };
        });
        break;
      }
      case "error": {
        setError(evt.message);
        setStreaming(false);
        setLiveTurn(null);
        break;
      }
      case "done": {
        setStreaming(false);
        setLiveTurn(null);
        refreshProjects();
        refreshDetail(evt.project.id);
        break;
      }
      default:
        break;
    }
  }, [refreshProjects, refreshDetail]);

  const sendMessage = useCallback(
    async (text) => {
      if (streaming || !text.trim()) return;
      setError(null);
      setStreaming(true);
      setLivePrd(null);
      setLiveTurn({ input: text, reply: "", steps: [] });
      try {
        await api.streamChat({ message: text, projectId: activeId, onEvent });
      } catch (e) {
        setError(e.message || String(e));
        setStreaming(false);
        setLiveTurn(null);
      }
    },
    [streaming, activeId, onEvent]
  );

  const prd = livePrd || detail?.prd || null;
  const memory = detail?.memory || [];
  const displayMessages = [
    ...(detail?.messages || []),
    ...(liveTurn
      ? [
          { id: "live-user", role: "user", content: liveTurn.input, steps: [] },
          {
            id: "live-assistant",
            role: "assistant",
            content: liveTurn.reply,
            steps: liveTurn.steps,
            pending: true,
          },
        ]
      : []),
  ];

  if (!auth) {
    return <AuthScreen onAuthed={handleAuthed} />;
  }

  return (
    <div className="app">
      <Sidebar
        projects={projects}
        activeId={activeId}
        username={auth.username}
        onSelect={selectProject}
        onNew={newProject}
        onDelete={handleDelete}
        onLogout={handleLogout}
        onOpenSettings={() => setSettingsOpen(true)}
      />
      <main className="main">
        <ChatArea
          project={detail?.project || (activeId ? { id: activeId, name: "加载中…", version: 0 } : null)}
          hasProject={!!activeId}
          messages={displayMessages}
          streaming={streaming}
          demoMode={demoMode}
          error={error}
          prdExists={!!prd}
          onSend={sendMessage}
          onTogglePanel={() => setPanelOpen((v) => !v)}
          panelOpen={panelOpen}
        />
      </main>
      {panelOpen && (
        <aside className="panel">
          <PrdPanel prd={prd} memory={memory} projectId={activeId} streaming={streaming} onToast={showToast} />
        </aside>
      )}
      {settingsOpen && (
        <SettingsModal
          onClose={() => setSettingsOpen(false)}
          onSaved={async () => {
            setSettingsOpen(false);
            showToast("✅ LLM 配置已保存，立即生效");
            try {
              const h = await api.health();
              setDemoMode(h.demo_mode);
            } catch {}
          }}
        />
      )}
      {toast && <div className="toast">{toast}</div>}
    </div>
  );
}

function nodeSummary(evt) {
  const d = evt;
  switch (d.name) {
    case "planner": {
      const intent = { create: "新需求分析", modify: "修改 PRD", question: "解答疑问" }[d.intent] || "";
      const plan = (d.plan || []).map((p) => p.title).join(" → ");
      return `${intent}｜${plan}`;
    }
    case "research_summary":
      return (d.summary || "").slice(0, 200);
    case "draft_prd":
      return `生成/更新 PRD，修改点 ${(d.changes || []).length} 项`;
    case "review": {
      const r = d.review || {};
      return `评分 ${r.score ?? "-"}，${r.passed ? "通过" : "不通过"}`;
    }
    case "update_memory":
      return `更新记忆 ${(d.updates || []).length} 条`;
    case "finalize":
      return (d.text || "").slice(0, 200);
    default:
      return "";
  }
}
