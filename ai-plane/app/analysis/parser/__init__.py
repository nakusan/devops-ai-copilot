"""Analysis 解析入口（兼容旧 stub 路径 app.analysis.parser）。"""

from app.analysis.parser.keyword_analyzer import analyze_text_sample, build_summary
from app.analysis.parser.text_sampler import sample_text

__all__ = ["analyze_text_sample", "build_summary", "sample_text"]
