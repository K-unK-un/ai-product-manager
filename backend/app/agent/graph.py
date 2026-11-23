"""LangGraph 图构建与 Agent 运行时。

Agent 拓扑（规划-执行-反思循环）：

    planner ──(question)──→ finalize
       │
       ├─(needs_research)→ research → tools(ToolNode) → research_summary ─┐
       │                                                                  ▼
       └───────────────(无需调研)────────────────────────────→ draft_prd ⇄ review
                                                                        │
                                          (不通过且未超限，携带反馈重写)┘
                                                                        │
                                                   (通过/达到上限) → update_memory → finalize → END
"""
import threading

from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from ..config import DATA_DIR, settings
from .nodes import (
    make_draft,
    make_finalize,
    make_memory,
    make_planner,
    make_research,
    make_research_summary,
    make_review,
    route_after_planner,
    route_after_review,
)
from .state import AgentState
from .tools import TOOLS

# 面向用户展示的节点名称（不暴露内部实现细节）
NODE_TITLES = {
    "planner": "任务规划",
    "research": "信息检索",
    "research_summary": "调研总结",
    "draft_prd": "撰写 PRD",
    "review": "质量自查",
    "update_memory": "记忆更新",
    "finalize": "生成回复",
}


def build_llm(cfg: dict | None = None):
    """按运行时配置构建 LLM。演示模式返回占位模型（不会被真正调用）。"""
    from ..llm_config import read_llm_config

    cfg = cfg or read_llm_config()
    if cfg["demo_mode"]:
        return FakeListChatModel(responses=[""])
    kwargs = dict(
        model=cfg["model"],
        api_key=cfg["api_key"],
        temperature=settings.llm_temperature,
    )
    if cfg.get("base_url"):
        kwargs["base_url"] = cfg["base_url"]
    return ChatOpenAI(**kwargs)


def build_graph(llm=None, demo_mode: bool = False, saver=None):
    """构建编译好的 LangGraph。llm/demo_mode/saver 均可注入（便于测试）。"""
    llm = llm or build_llm()

    g = StateGraph(AgentState)
    g.add_node("planner", make_planner(llm, demo_mode))
    g.add_node("research", make_research(llm, demo_mode))
    g.add_node("tools", ToolNode(TOOLS))
    g.add_node("research_summary", make_research_summary(llm, demo_mode))
    g.add_node("draft_prd", make_draft(llm, demo_mode))
    g.add_node("review", make_review(llm, demo_mode))
    g.add_node("update_memory", make_memory(llm, demo_mode))
    g.add_node("finalize", make_finalize(llm, demo_mode))

    g.set_entry_point("planner")
    g.add_conditional_edges("planner", route_after_planner,
                            {"finalize": "finalize", "research": "research", "draft_prd": "draft_prd"})
    g.add_edge("research", "tools")
    g.add_edge("tools", "research_summary")
    g.add_edge("research_summary", "draft_prd")
    g.add_edge("draft_prd", "review")
    g.add_conditional_edges("review", route_after_review,
                            {"update_memory": "update_memory", "draft_prd": "draft_prd"})
    g.add_edge("update_memory", "finalize")
    g.add_edge("finalize", END)

    return g.compile(checkpointer=saver)


class AgentRuntime:
    """进程级单例：按用户缓存 LLM 与图，共享检查点。

    LLM 配置按用户隔离（UserSetting 表），因此每个用户拥有独立的 LLM 与图；
    检查点按项目 thread_id 区分，用户之间互不影响。

    AsyncSqliteSaver.from_conn_string 返回的是异步上下文管理器，
    需要在 setup 中 __aenter__ 后才得到可用的 saver（其底层 aiosqlite
    连接绑定创建时的事件循环，因此随应用生命周期创建与销毁）。
    """

    def __init__(self):
        self.saver = None
        self._cache: dict[str, tuple[tuple, object, bool]] = {}
        self._lock = threading.Lock()

    async def setup(self) -> None:
        if self.saver is not None:
            return
        # 检查点：持久化每个项目会话的图执行状态，支持断点续跑
        self._saver_cm = AsyncSqliteSaver.from_conn_string(str(DATA_DIR / "checkpoints.sqlite"))
        self.saver = await self._saver_cm.__aenter__()
        await self.saver.setup()

    def get(self, user_id: str):
        """返回 (graph, demo_mode)；该用户配置变化时自动重建。"""
        from ..llm_config import read_llm_config

        cfg = read_llm_config(user_id)
        sig = (cfg["provider"], cfg["api_key"], cfg["model"], cfg["base_url"])
        with self._lock:
            cached = self._cache.get(user_id)
            if cached and cached[0] == sig:
                return cached[1], cached[2]
        llm = build_llm(cfg)
        graph = build_graph(llm, cfg["demo_mode"], self.saver)
        with self._lock:
            self._cache[user_id] = (sig, graph, cfg["demo_mode"])
        return graph, cfg["demo_mode"]

    def refresh(self, user_id: str | None = None) -> None:
        """配置保存后使缓存失效；user_id 为空时清空全部用户。"""
        with self._lock:
            if user_id is None:
                self._cache.clear()
            else:
                self._cache.pop(user_id, None)

    async def delete_thread(self, project_id: str) -> None:
        """删除项目的 LangGraph 检查点数据（项目删除后清理）。"""
        if self.saver is None:
            return
        thread_id = f"project-{project_id}"
        try:
            await self.saver.adelete_thread(thread_id)
            return
        except NotImplementedError:
            # 当前 langgraph-checkpoint-sqlite 版本未实现该方法，直接清理两张表
            conn = self.saver.conn
            async with self.saver.lock:
                await conn.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
                await conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
                await conn.commit()

    async def close(self) -> None:
        if self.saver is not None:
            await self._saver_cm.__aexit__(None, None, None)
            self.saver = None
        self.refresh()


_AGENT: AgentRuntime | None = None


def get_agent() -> AgentRuntime:
    global _AGENT
    if _AGENT is None:
        _AGENT = AgentRuntime()
    return _AGENT
