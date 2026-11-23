import { useEffect, useState } from "react";
import { api } from "../api.js";

// 当前版本前端只开放 DeepSeek，其他服务商暂不接入
const PROVIDER = "deepseek";
const PROVIDER_LABEL = "DeepSeek（国内直连）";

export default function SettingsModal({ onClose, onSaved }) {
  const [form, setForm] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.getLlmSettings()
      .then((cfg) =>
        setForm({
          provider: cfg.provider,
          api_key: "",
          model: cfg.model,
          base_url: cfg.base_url || "",
          has_api_key: cfg.has_api_key,
          api_key_masked: cfg.api_key_masked,
          demo_mode: cfg.demo_mode,
        })
      )
      .catch((e) => setError(e.message));
  }, []);

  const set = (key, value) => setForm((f) => ({ ...f, [key]: value }));

  const save = async () => {
    setError(null);
    setBusy(true);
    try {
      const updates = { provider: PROVIDER, model: form.model.trim() || null };
      if (form.api_key.trim()) updates.api_key = form.api_key.trim();
      if (form.base_url.trim()) updates.base_url = form.base_url.trim();
      await api.saveLlmSettings(updates);
      onSaved();
    } catch (e) {
      setError(e.message || "保存失败");
    } finally {
      setBusy(false);
    }
  };

  const clearKey = async () => {
    setBusy(true);
    try {
      await api.saveLlmSettings({ api_key: "" });
      onSaved();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div className="modal-title">⚙️ LLM 配置</div>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        {!form ? (
          <div className="modal-body">加载中…</div>
        ) : (
          <div className="modal-body">
            <div className={`cfg-status ${form.demo_mode ? "warn" : "ok"}`}>
              {form.demo_mode
                ? "当前：演示模式（未配置可用 API Key，Agent 流程真实执行、内容为模板）"
                : `当前：已配置 ${form.provider} / ${form.model}`}
            </div>

            <div className="form-row">
              <label className="form-label">服务商</label>
              <input className="form-input" value={PROVIDER_LABEL} disabled />
              <div className="form-hint">当前版本仅支持 DeepSeek，其他服务商暂未开放。</div>
            </div>

            <div className="form-row">
              <label className="form-label">API Key</label>
              <div className="form-inline">
                <input
                  className="form-input"
                  type="password"
                  placeholder={form.has_api_key ? `已保存（${form.api_key_masked}），留空保持不变` : "粘贴 DeepSeek API Key"}
                  value={form.api_key}
                  onChange={(e) => set("api_key", e.target.value)}
                />
                {form.has_api_key && (
                  <button className="btn-link" onClick={clearKey}>清除</button>
                )}
              </div>
              <div className="form-hint">该 Key 同时用于 DeepSeek 官方联网搜索；清除后自动回到演示模式（流程真实执行、内容为模板）。</div>
            </div>
            <div className="form-row">
              <label className="form-label">模型名称</label>
              <input className="form-input" placeholder="deepseek-chat" value={form.model} onChange={(e) => set("model", e.target.value)} />
            </div>
            <div className="form-row">
              <label className="form-label">API 地址（可选）</label>
              <input className="form-input" placeholder="留空使用 https://api.deepseek.com/v1" value={form.base_url} onChange={(e) => set("base_url", e.target.value)} />
            </div>

            {error && <div className="auth-error">⚠ {error}</div>}

            <div className="modal-actions">
              <button className="btn-ghost" onClick={onClose}>取消</button>
              <button className="btn-primary" disabled={busy} onClick={save}>
                {busy ? "保存中…" : "保存并生效"}
              </button>
            </div>
            <div className="form-hint">保存后立即生效（热更新），无需重启服务；API Key 仅保存在服务器本地数据库中。</div>
          </div>
        )}
      </div>
    </div>
  );
}
