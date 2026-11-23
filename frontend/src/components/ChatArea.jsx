import { useEffect, useRef, useState } from "react";
import ExecutionSteps from "./ExecutionSteps.jsx";

const IDEA_CHIPS = [
  "AI 健身教练 App，为健身新手生成个性化训练计划",
  "面向大学生的二手书交易平台",
  "宠物寄养预约小程序",
  "远程团队 OKR 协作工具",
  "考研刷题与打卡社区",
];

const MODIFY_CHIPS = [
  "补充数据指标体系",
  "把目标用户改成大学生",
  "增加会员订阅商业模式",
  "再做一轮竞品分析",
];

export default function ChatArea({
  project,
  hasProject,
  messages,
  streaming,
  demoMode,
  error,
  prdExists,
  onSend,
  onTogglePanel,
  panelOpen,
}) {
  const [input, setInput] = useState("");
  const scrollRef = useRef(null);
  const inputRef = useRef(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  useEffect(() => {
    if (hasProject) inputRef.current?.focus();
  }, [hasProject]);

  const submit = (text) => {
    if (!text || !text.trim() || streaming) return;
    setInput("");
    onSend(text.trim());
  };

  return (
    <div className="chat">
      <header className="chat-header">
        <div className="chat-header-left">
          <div className="chat-title">
            {hasProject ? (project?.name || "项目") : "新建项目"}
            {hasProject && project?.version > 0 && (
              <span className="badge-version">v{project.version}</span>
            )}
          </div>
          <div className="chat-subtitle">
            {hasProject ? "多轮对话修改 PRD · 上策会记住产品上下文" : "一句话描述你的产品想法"}
          </div>
        </div>
        <button className="btn-ghost" onClick={onTogglePanel} title="切换右侧 PRD 面板">
          {panelOpen ? "隐藏 PRD ›" : "‹ 显示 PRD"}
        </button>
      </header>

      {demoMode === true && (
        <div className="demo-banner">
          ⚡ 当前为<strong>演示模式</strong>（未配置 LLM API Key）：Agent 流程与工具调用真实执行，内容为模板。
          点击左下角 <strong>⚙️ 设置</strong> 填入 DeepSeek API Key 后自动切换真实 AI。
        </div>
      )}

      <div className="chat-scroll" ref={scrollRef}>
        {!hasProject && (
          <div className="welcome">
            <div className="welcome-logo">上策</div>
            <h1>输入产品想法，生成结构化 PRD</h1>
            <p className="welcome-sub">
              AI 产品经理 Agent 将自动完成需求分析、竞品调研、PRD 撰写与质量自查，
              并支持多轮对话持续修改
            </p>
            <div className="welcome-input">
              <textarea
                ref={inputRef}
                rows={3}
                placeholder="例：做一个面向健身新手的 AI 健身教练 App，核心功能是生成个性化训练计划…"
                value={input}
                disabled={streaming}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    submit(input);
                  }
                }}
              />
              <button className="btn-primary" disabled={streaming || !input.trim()} onClick={() => submit(input)}>
                {streaming ? "分析中…" : "生成 PRD →"}
              </button>
            </div>
            <div className="chips">
              {IDEA_CHIPS.map((c) => (
                <button key={c} className="chip" disabled={streaming} onClick={() => submit(c)}>
                  💡 {c}
                </button>
              ))}
            </div>
          </div>
        )}

        {hasProject && (
          <div className="msg-list">
            {messages.map((m) => (
              <div key={m.id} className={`msg ${m.role}`}>
                {m.role === "assistant" && <div className="avatar">📐</div>}
                <div className="msg-body">
                  <div className="bubble">
                    {m.content ? (
                      <span className="bubble-text">
                        {m.content.split("\n").map((line, i) => (
                          <span key={i}>
                            {line}
                            {i < m.content.split("\n").length - 1 && <br />}
                          </span>
                        ))}
                      </span>
                    ) : m.pending ? (
                      <span className="typing">
                        <i />
                        <i />
                        <i />
                      </span>
                    ) : null}
                  </div>
                  {m.steps && m.steps.length > 0 && <ExecutionSteps steps={m.steps} pending={m.pending} />}
                </div>
              </div>
            ))}
          </div>
        )}

        {error && <div className="error-toast">⚠ {error}</div>}
      </div>

      {hasProject && (
        <footer className="composer">
          {!streaming && prdExists && (
            <div className="chips chips-modify">
              {MODIFY_CHIPS.map((c) => (
                <button key={c} className="chip" onClick={() => submit(c)}>
                  ✏️ {c}
                </button>
              ))}
            </div>
          )}
          <div className="composer-box">
            <textarea
              rows={1}
              placeholder={streaming ? "上策正在工作…" : "提出修改意见或继续提问，Enter 发送"}
              value={input}
              disabled={streaming}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit(input);
                }
              }}
            />
            <button className="btn-send" disabled={streaming || !input.trim()} onClick={() => submit(input)}>
              {streaming ? "…" : "发送"}
            </button>
          </div>
        </footer>
      )}
    </div>
  );
}
