"""工具 registry / intent 推导。"""

from app.graph.tools.registry import TOOL_KIND, build_openai_tools, derive_intent


def test_build_tools_respects_flags() -> None:
    tools = build_openai_tools(
        {"enable_rag": False, "enable_mcp": False, "mcp_servers": []}
    )
    names = {t["function"]["name"] for t in tools}
    assert "retrieve_knowledge" not in names
    assert "prometheus_query" not in names
    assert "list_analysis_jobs" in names
    assert "get_analysis_job" in names


def test_build_tools_includes_rag_and_prom() -> None:
    tools = build_openai_tools(
        {"enable_rag": True, "enable_mcp": True, "mcp_servers": ["prometheus"]}
    )
    names = {t["function"]["name"] for t in tools}
    assert "retrieve_knowledge" in names
    assert "prometheus_query" in names
    assert "readonly_sql" not in names


def test_derive_intent() -> None:
    assert derive_intent(set()) == "direct"
    assert derive_intent({"retrieve_knowledge"}) == "rag"
    assert derive_intent({"prometheus_query"}) == "tool"
    assert derive_intent({"retrieve_knowledge", "prometheus_query"}) == "rag_and_tool"
    assert derive_intent({"list_analysis_jobs"}) == "analysis"
    assert derive_intent({"list_analysis_jobs", "retrieve_knowledge"}) == "analysis"
    assert set(TOOL_KIND) >= {
        "retrieve_knowledge",
        "prometheus_query",
        "readonly_sql",
        "list_analysis_jobs",
        "get_analysis_job",
    }
