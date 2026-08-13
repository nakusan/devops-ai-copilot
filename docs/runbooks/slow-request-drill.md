# 慢请求排障演练（MVP）

> 对应设计书 6.7 / **6.10**：能完成一次「慢请求」人工排障演练。  
> **原则：先看 trace，再看指标尖峰，最后才翻日志。**

## 前置

1. `make infra-up` 或 `make stack-up`（含 Prometheus :9090、Grafana :23000、Tempo）
2. 本机或 Compose 启动 control-plane (:8080) 与 ai-plane (:8000) + worker
3. 确认：
   - Prometheus targets UP：http://localhost:9090/targets
   - Grafana Tempo Explore 能搜到 `service.name=ai-plane`（至少有一条聊天或健康检查相关 trace）

## 步骤（Trace-first）

1. 发起一次聊天（含 RAG 或 MCP 意图，例如「当前数据库连接数正常吗？」）或上传一份知识库文档（验证 Kafka 异步链）
2. 从响应头取出 `X-Trace-Id`（值应等于 Tempo 中的 traceId）
3. **Grafana → Explore → Tempo**：用该 traceId 打开整棵 span 树
   - 同步聊天：应同时看到 `control-plane` 与 `ai-plane`（P2）
   - 关注耗时大户：`rag.retrieve` / asyncpg `SELECT` / `rag.embed` / `llm.completion`（看 `llm.ttfb_ms`、`gen_ai.usage.*`）
   - 异步入库：同一条 trace 应含 Kafka producer → `{topic} receive` → `ingest.process` → 回写 Java（P3）
4. **Grafana → Overview Dashboard**
   - 「慢请求 / Error / Slow RAG」TraceQL 面板作入口
   - Chat / RAG / LLM histogram：若开启 exemplars，尖峰点可点进对应 trace
5. 仅在 trace 仍不足以定位时，再用同一 `traceId` 搜日志：
   - Java：`event=chat.stream.end`
   - Python：`chat.stream.end` / `diagnosis graph done` / ingest 序号日志
6. 将结论写入一份 [Postmortem](./postmortem-template.md) 练习稿（字段：现象、根因 span、影响面、改进项）

## 注入故障对照（可选）

| 注入 | 预期观测（优先在 Tempo） |
|------|--------------------------|
| 停 Redis | 限流异常；chat 可能仍可用 |
| LLM 超时 | `llm.completion` 拉长或 error；`llm_time_to_first_token` 升高；`chat.errors{code=LLM_TIMEOUT}` |
| 停 Kafka | 上传链路无 consumer span；`kafka_publish_failures` / ingest PENDING |
| Embedding 慢 | `rag.embed` 子 span 突出 |

## 验收勾选（对标 6.10 §10）

- [ ] 用 `X-Trace-Id` 在 Tempo 打开完整 span 树
- [ ] 能指出瓶颈 span（而非仅凭 P99 猜）
- [ ] 产出一份 Postmortem 练习稿
