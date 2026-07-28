"""进行中生成任务的取消注册表。

Java 在 SSE 断开时调用 /internal/v1/chat/cancel，本表将对应 session 的 Event set，
Mock/LLM 循环检测到后停止 yield，避免客户端已走仍继续烧 Token。
"""

import asyncio


class CancelRegistry:
    def __init__(self) -> None:
        self._events: dict[str, asyncio.Event] = {}

    def register(self, session_id: str) -> asyncio.Event:
        # 同一 session 重复请求：覆盖旧 Event，旧流读到后也会尽快退出
        ev = asyncio.Event()
        self._events[session_id] = ev
        return ev

    def cancel(self, session_id: str) -> bool:
        ev = self._events.get(session_id)
        if ev is None:
            return False
        ev.set()
        return True

    def unregister(self, session_id: str) -> None:
        self._events.pop(session_id, None)


cancel_registry = CancelRegistry()
