# 慢请求排障演练（MVP）

> 对应设计书 6.7 验收项：能完成一次「慢请求」人工排障演练。

## 前置

1. `make infra-up`（含 Prometheus :9090、Grafana :3000）
2. 本机启动 control-plane (:8080) 与 ai-plane (:8000)
3. 确认 Prometheus targets UP：http://localhost:9090/targets

## 步骤

1. 发起一次聊天（含 RAG 或 MCP 意图，例如「当前数据库连接数正常吗？」）
2. 从响应头或错误体取出 `X-Trace-Id` / `traceId`
3. Grafana Overview：观察 Chat QPS、P99、LLM TTFB、MCP P99
4. 日志检索：
   - Java：`event=chat.stream.end` + 该 `traceId`
   - Python：同 `traceId` 的 `chat.stream.end` / `diagnosis graph done`
5. 判断瓶颈在 Java 编排、RAG、MCP 还是 LLM TTFB
6. 将结论写入一份 [Postmortem](./postmortem-template.md) 练习稿

## 注入故障对照（可选）

| 注入 | 预期观测 |
|------|----------|
| 停 Redis | 限流异常日志；chat 可能仍可用 |
| LLM 超时 | `llm_time_to_first_token` 升高；`chat.errors{code=LLM_TIMEOUT}` |
| 停 Kafka | `kafka_publish_failures`；ingest PENDING |
