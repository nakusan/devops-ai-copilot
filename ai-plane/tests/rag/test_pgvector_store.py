"""pgvector_store metadata 解析单元测试。"""

from app.rag.retrieval.pgvector_store import _parse_metadata_json


def test_parse_metadata_json_string() -> None:
    """asyncpg 默认返回 JSON 字符串，不能用 dict(str)。"""
    assert _parse_metadata_json('{"embedding_model_version": "v1", "source": "seed"}') == {
        "embedding_model_version": "v1",
        "source": "seed",
    }
    assert _parse_metadata_json("{}") == {}
    assert _parse_metadata_json("") == {}
    assert _parse_metadata_json(None) == {}


def test_parse_metadata_json_dict() -> None:
    raw = {"embedding_model_version": "v1"}
    parsed = _parse_metadata_json(raw)
    assert parsed == raw
    assert parsed is not raw


def test_parse_metadata_json_invalid_or_non_object() -> None:
    assert _parse_metadata_json("[]") == {}
    assert _parse_metadata_json('"x"') == {}
    assert _parse_metadata_json("{not-json") == {}
    assert _parse_metadata_json(b'{"a": 1}') == {"a": 1}
