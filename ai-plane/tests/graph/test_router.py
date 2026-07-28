"""RouterNode 意图分类单元测试。"""

from app.graph.nodes.router import router_node
from app.graph.state import DiagnosisState


def _state(msg: str, *, enable_rag: bool = True, enable_mcp: bool = True) -> DiagnosisState:
    return DiagnosisState(
        user_message=msg,
        agent_config={"enable_rag": enable_rag, "enable_mcp": enable_mcp},
    )


def test_router_analysis_intent() -> None:
    out = router_node(_state("我上传的 heap 分析结果呢？"))
    assert out["intent"] == "analysis"


def test_router_rag_and_tool_parallel() -> None:
    out = router_node(_state("STATUS_899 是什么？当前连接数正常吗？"))
    assert out["intent"] == "rag_and_tool"


def test_router_tool_only() -> None:
    out = router_node(_state("当前 DB 连接数多少？"))
    assert out["intent"] == "tool"


def test_router_rag_only() -> None:
    out = router_node(_state("STATUS_899 是什么原因？"))
    assert out["intent"] == "rag"


def test_router_direct_when_rag_disabled() -> None:
    out = router_node(_state("你好", enable_rag=False))
    assert out["intent"] == "direct"


def test_router_default_rag_for_ops() -> None:
    out = router_node(_state("你好"))
    assert out["intent"] == "rag"
