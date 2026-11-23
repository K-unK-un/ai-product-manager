const INTENT_EMOJI = { create: "💡", modify: "✏️", question: "❓" };

export default function Sidebar({
  projects,
  activeId,
  username,
  onSelect,
  onNew,
  onDelete,
  onLogout,
  onOpenSettings,
}) {
  return (
    <nav className="sidebar">
      <div className="brand">
        <div className="brand-logo">上策</div>
        <div className="brand-sub">AI 产品经理</div>
      </div>

      <button className="btn-new" onClick={onNew}>
        <span className="btn-new-plus">＋</span> 新建项目
      </button>

      <div className="project-list">
        <div className="project-list-title">项目列表</div>
        {projects.length === 0 && (
          <div className="project-empty">还没有项目<br />输入一个产品想法开始</div>
        )}
        {projects.map((p) => (
          <div
            key={p.id}
            className={`project-item ${p.id === activeId ? "active" : ""}`}
            onClick={() => onSelect(p.id)}
          >
            <div className="project-item-main">
              <div className="project-item-name" title={p.name}>
                {p.name || "未命名产品"}
              </div>
              <div className="project-item-meta">
                {p.has_prd ? <span className="badge-version">v{p.version}</span> : <span className="badge-draft">草稿</span>}
                <span className="project-item-time">{timeAgo(p.updated_at)}</span>
              </div>
            </div>
            <button
              className="project-item-del"
              title="删除项目"
              onClick={(e) => {
                e.stopPropagation();
                if (window.confirm(`删除项目「${p.name}」？此操作不可恢复。`)) onDelete(p.id);
              }}
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      <div className="sidebar-footer">
        <div className="user-row">
          <span className="user-name" title={username}>👤 {username}</span>
          <div className="user-actions">
            <button className="footer-btn" title="LLM 配置" onClick={onOpenSettings}>⚙️</button>
            <button className="footer-btn" title="退出登录" onClick={onLogout}>⎋</button>
          </div>
        </div>
        <div className="sidebar-footer-tech">LangChain · LangGraph</div>
      </div>
    </nav>
  );
}

function timeAgo(iso) {
  if (!iso) return "";
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "刚刚";
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  return `${Math.floor(diff / 86400)} 天前`;
}
