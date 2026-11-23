import { useState } from "react";
import { api, setToken } from "../api.js";

export default function AuthScreen({ onAuthed }) {
  const [mode, setMode] = useState("login"); // login | register
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setError(null);
    if (!username.trim() || !password) {
      setError("请输入用户名和密码");
      return;
    }
    if (mode === "register" && password !== confirm) {
      setError("两次输入的密码不一致");
      return;
    }
    setBusy(true);
    try {
      const fn = mode === "login" ? api.login : api.register;
      const data = await fn(username.trim(), password);
      setToken(data.token); // 保存令牌，后续请求自动携带
      onAuthed({ username: data.username });
    } catch (e) {
      setError(e.message || "操作失败");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth-screen">
      <div className="auth-card">
        <div className="auth-brand">上策</div>
        <div className="auth-sub">AI 产品经理 · 把想法变成可落地的产品方案</div>

        <div className="auth-tabs">
          <button className={mode === "login" ? "active" : ""} onClick={() => { setMode("login"); setError(null); }}>
            登录
          </button>
          <button className={mode === "register" ? "active" : ""} onClick={() => { setMode("register"); setError(null); }}>
            注册
          </button>
        </div>

        <div className="auth-form">
          <input
            className="auth-input"
            placeholder="用户名（3~32 字符）"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
          />
          <input
            className="auth-input"
            type="password"
            placeholder="密码（至少 6 位）"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
          />
          {mode === "register" && (
            <input
              className="auth-input"
              type="password"
              placeholder="确认密码"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && submit()}
            />
          )}
          {error && <div className="auth-error">⚠ {error}</div>}
          <button className="btn-primary auth-submit" disabled={busy} onClick={submit}>
            {busy ? "请稍候…" : mode === "login" ? "登录" : "注册并登录"}
          </button>
        </div>

        <div className="auth-hint">
          {mode === "login" ? "还没有账号？" : "已有账号？"}
          <a onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(null); }}>
            {mode === "login" ? "立即注册" : "去登录"}
          </a>
        </div>
      </div>
    </div>
  );
}
