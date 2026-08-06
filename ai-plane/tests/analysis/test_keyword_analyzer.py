"""关键字分析器单元测试。"""

from app.analysis.parser.keyword_analyzer import analyze_text_sample, build_summary


def test_analyze_and_summary():
    text = (
        "OutOfMemoryError happened. Full GC. "
        "java.lang.NullPointerException and IOException ERROR"
    )
    parsed = analyze_text_sample(text, "APP_LOG")
    assert parsed["keyword_counts"]["OOM"] >= 1
    assert parsed["keyword_counts"]["FULL_GC"] >= 1
    assert "java.lang.NullPointerException" in parsed["top_exceptions"]
    summary = build_summary(parsed)
    assert "OOM" in summary
    assert len(summary) < 2048
