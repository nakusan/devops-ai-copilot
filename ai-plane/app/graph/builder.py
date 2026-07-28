"""LangGraph 诊断 DAG 构图 + compile（MVP 无 checkpointer）。"""

from langgraph.graph import END, StateGraph

from app.graph.nodes.analysis import analysis_lookup_node
from app.graph.nodes.fan_out import fan_out_node
from app.graph.nodes.retrieve import retrieve_node
from app.graph.nodes.router import route_by_intent, router_node
from app.graph.nodes.synthesize import synthesize_node
from app.graph.nodes.tool import tool_node
from app.graph.state import DiagnosisState

# 编译后图单例，进程内复用
_compiled_graph = None


def build_diagnosis_graph():
    """硬编码 MVP DAG（6.5 §3.4）。

    MVP 不挂 Redis checkpointer：对话 history 由 Java PG 传入（P7）。
    """
    g = StateGraph(DiagnosisState)

    g.add_node("router", router_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("tool", tool_node)
    g.add_node("fan_out", fan_out_node)
    g.add_node("analysis", analysis_lookup_node)
    g.add_node("synthesize", synthesize_node)

    g.set_entry_point("router")

    g.add_conditional_edges(
        "router",
        route_by_intent,
        {
            "rag": "retrieve",
            "tool": "tool",
            "rag_and_tool": "fan_out",
            "analysis": "analysis",
            "direct": "synthesize",
        },
    )

    g.add_edge("retrieve", "synthesize")
    g.add_edge("tool", "synthesize")
    g.add_edge("fan_out", "synthesize")
    g.add_edge("analysis", "synthesize")
    g.add_edge("synthesize", END)

    return g.compile()


def get_diagnosis_graph():
    """懒加载编译图，避免 import 时重复 compile。"""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_diagnosis_graph()
    return _compiled_graph
