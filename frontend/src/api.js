// 后端 API 封装（含登录令牌管理与 401 处理）
const BASE = "";

let _token = localStorage.getItem("shangce_token") || "";
let _onUnauthorized = null;

export function getToken() {
  return _token;
}

export function setToken(token) {
  _token = token || "";
  if (token) localStorage.setItem("shangce_token", token);
  else localStorage.removeItem("shangce_token");
}

export function setOnUnauthorized(fn) {
  _onUnauthorized = fn;
}

async function request(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (_token) headers["Authorization"] = "Bearer " + _token;
  const resp = await fetch(BASE + url, { ...options, headers });
  if (resp.status === 401) {
    setToken("");
    if (_onUnauthorized) _onUnauthorized();
    throw new Error("登录已过期，请重新登录");
  }
  if (!resp.ok) {
    let msg = `请求失败 (${resp.status})`;
    try {
      const body = await resp.json();
      if (body.detail) msg = body.detail;
    } catch {}
    throw new Error(msg);
  }
  return resp.json();
}

export const api = {
  // ---- 认证 ----
  register: (username, password) =>
    request("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }),
  login: (username, password) =>
    request("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    }),
  me: () => request("/api/auth/me"),

  // ---- 项目 ----
  listProjects: () => request("/api/projects"),
  getProject: (id) => request(`/api/projects/${id}`),
  deleteProject: async (id) => {
    const headers = {};
    if (_token) headers["Authorization"] = "Bearer " + _token;
    const resp = await fetch(`${BASE}/api/projects/${id}`, { method: "DELETE", headers });
    if (!resp.ok) throw new Error("删除失败");
  },
  // 导出 PRD 为 Markdown：普通 <a href> 带不上 Authorization 头，需用 fetch + Blob 下载
  exportPrd: async (id) => {
    const headers = {};
    if (_token) headers["Authorization"] = "Bearer " + _token;
    const resp = await fetch(`${BASE}/api/projects/${id}/prd.md`, { headers });
    if (resp.status === 401) {
      setToken("");
      if (_onUnauthorized) _onUnauthorized();
      throw new Error("登录已过期，请重新登录");
    }
    if (!resp.ok) {
      let msg = `导出失败 (${resp.status})`;
      try {
        const body = await resp.json();
        if (body.detail) msg = body.detail;
      } catch {}
      throw new Error(msg);
    }
    const blob = await resp.blob();
    let filename = "PRD.md";
    const cd = resp.headers.get("Content-Disposition") || "";
    const m = cd.match(/filename\*=UTF-8''([^;]+)/i);
    if (m) {
      try { filename = decodeURIComponent(m[1]); } catch {}
    }
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  },
  health: () => request("/api/health"),

  // ---- LLM 配置 ----
  getLlmSettings: () => request("/api/settings/llm"),
  saveLlmSettings: (updates) =>
    request("/api/settings/llm", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(updates),
    }),

  /**
   * SSE 流式聊天。
   * @param {{message: string, projectId: string|null, onEvent: (evt: object) => void}} opts
   */
  async streamChat({ message, projectId, onEvent }) {
    const headers = { "Content-Type": "application/json" };
    if (_token) headers["Authorization"] = "Bearer " + _token;
    const resp = await fetch(`${BASE}/api/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify({ message, project_id: projectId }),
    });
    if (resp.status === 401) {
      setToken("");
      if (_onUnauthorized) _onUnauthorized();
      throw new Error("登录已过期，请重新登录");
    }
    if (!resp.ok || !resp.body) {
      let msg = `请求失败 (${resp.status})`;
      try {
        const body = await resp.json();
        if (body.detail) msg = body.detail;
      } catch {}
      throw new Error(msg);
    }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const chunk = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        for (const line of chunk.split("\n")) {
          if (line.startsWith("data: ")) {
            try {
              onEvent(JSON.parse(line.slice(6)));
            } catch {}
          }
        }
      }
    }
  },
};
