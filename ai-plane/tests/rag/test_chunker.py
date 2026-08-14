"""切块器 / 清洗器单元测试。"""

from app.rag.pipeline.chunker import ChunkConfig, chunk_text
from app.rag.pipeline.cleaner import clean


def test_clean_collapses_whitespace():
    assert "a b" in clean("a   b\n\n\n\nc")


def test_clean_strips_toc_leaders_and_keeps_body():
    raw = (
        "擎天-统一门户操作手册\n"
        "1 概述 ................................................ 5\n"
        "2 登录 ................................................ 6\n"
        "........ 9\n"
        "3.1.3 消息中心 ........................................ 10\n"
        "第 1 页\n"
        "用户在浏览器中输入运营管理平台地址后，进入统一身份认证页面。\n"
    )
    out = clean(raw)
    assert "...." not in out
    assert "第 1 页" not in out
    assert "统一身份认证页面" in out


def test_clean_fullwidth_dots_become_toc_after_nfkc():
    raw = "2 登录 " + ("．" * 20) + " 6\n正文从这里开始，包含足够多的汉字以便通过信息量过滤。"
    out = clean(raw)
    assert "...." not in out
    assert "正文从这里开始" in out


def test_clean_keeps_page_sentinel():
    raw = "<!-- page:3 -->\n登录成功后进入控制台首页，可以看到待办与消息入口。"
    out = clean(raw)
    assert "<<<PAGE:3>>>" in out
    assert "<!-- page" not in out.lower()


def test_chunk_respects_size_and_overlap():
    text = ("段落甲。\n\n" + "字" * 50 + "\n\n") * 20
    chunks = chunk_text(text, ChunkConfig(chunk_size=80, chunk_overlap=10))
    assert len(chunks) >= 2
    assert all(len(c.content) <= 80 + 10 for c in chunks)
    assert chunks[0].chunk_index == 0
    assert chunks[-1].chunk_index == len(chunks) - 1


def test_heading_aware_keeps_section_together():
    text = (
        "# 2 登录\n"
        "用户在浏览器中输入运营管理平台地址后，进入统一身份认证页面。"
        "连续五次密码错误将锁定账号十五分钟。\n\n"
        "# 3.1.3 消息中心\n"
        "平台内所有系统通知、审批提醒与告警都会汇聚到统一的通知面板中。"
    )
    chunks = chunk_text(text, ChunkConfig(chunk_size=512, chunk_overlap=0))
    login = [c for c in chunks if "锁定账号" in c.content]
    msg = [c for c in chunks if "通知面板" in c.content]
    assert len(login) == 1
    assert len(msg) == 1
    assert "通知面板" not in login[0].content
    assert "锁定账号" not in msg[0].content
    assert login[0].metadata["heading"] == "2 登录"
    assert "消息中心" in msg[0].metadata["heading"]
    assert login[0].content.startswith("[2 登录]")


def test_numbered_heading_without_hash():
    text = (
        "2 登录\n"
        "用户在浏览器中输入运营管理平台地址后完成认证，连续五次密码错误将锁定账号。\n"
        "3.1.3 消息中心\n"
        "平台内所有系统通知都会汇聚到统一的通知面板中，未读条目以蓝色圆点标记。"
    )
    chunks = chunk_text(text, ChunkConfig(chunk_size=512, chunk_overlap=0))
    assert len(chunks) == 2
    assert chunks[0].metadata["heading"] == "2 登录"
    assert chunks[1].metadata["heading"].endswith("3.1.3 消息中心")


def test_page_metadata_from_sentinel():
    text = (
        "<<<PAGE:6>>>\n2 登录\n"
        "用户在浏览器中输入地址后进入统一身份认证页面，输入账号密码即可登录系统。"
    )
    chunks = chunk_text(text, ChunkConfig(chunk_size=512, chunk_overlap=0))
    assert chunks
    assert chunks[0].metadata["page"] == 6
    assert "<<<PAGE" not in chunks[0].content


def test_drops_low_information_and_records_stats():
    text = (
        "................................ 12\n"
        "|||| |||| ||||\n"
        "2 登录\n"
        "用户在浏览器中输入运营管理平台地址后，进入统一身份认证页面完成登录。"
    )
    stats: dict = {}
    chunks = chunk_text(
        text,
        ChunkConfig(chunk_size=512, chunk_overlap=0, min_substantive_chars=20),
        stats=stats,
    )
    assert all("...." not in c.content for c in chunks)
    assert any("统一身份认证" in c.content for c in chunks)
    assert stats["dropped"] >= 1


def test_clean_then_chunk_toc_heavy_manual():
    """入库真实路径：先 clean 再 chunk，目录不得进入最终块。"""
    raw = (
        "<!-- page:1 -->擎天-统一门户操作手册\n"
        "1 概述 ................................................ 5\n"
        "1.1 编写目的 .......................................... 5\n"
        "2 登录 ................................................ 6\n"
        "3.1.3 消息中心 ........................................ 10\n"
        "3.2.6 服务续订 ........................................ 14\n"
        "<!-- page:6 -->\n"
        "2 登录\n"
        "用户在浏览器中输入运营管理平台地址后，进入统一身份认证页面。"
        "连续五次密码错误将锁定账号十五分钟，可联系管理员解锁。\n"
        "<!-- page:10 -->\n"
        "3.1.3 消息中心\n"
        "平台内所有系统通知、审批提醒与告警都会汇聚到统一的通知面板中。"
        "未读条目以蓝色圆点标记，支持按时间范围筛选。\n"
    )
    chunks = chunk_text(clean(raw), ChunkConfig(chunk_size=512, chunk_overlap=64))
    joined = "\n".join(c.content for c in chunks)
    assert "...." not in joined
    assert "锁定账号" in joined
    assert "通知面板" in joined
    login = next(c for c in chunks if "锁定账号" in c.content)
    assert login.metadata.get("page") == 6
    assert all(c.chunk_index == i for i, c in enumerate(chunks))
