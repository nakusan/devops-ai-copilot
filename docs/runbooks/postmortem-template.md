# 事故复盘模板（Postmortem）

> 设计书 6.7 §3.8.2。用于「慢请求 / 故障」演练与真实事故记录。

---

## 事故标题

- 时间：
- 影响范围（用户数 / 会话数 / 接口）：
- 严重级别：
- traceId 样例：

## 时间线

| 时间 | 事件 |
|------|------|
| | 用户报障 / 告警 |
| | 开始排查 |
| | 定位根因 |
| | 缓解 / 修复 |
| | 恢复确认 |

## 根因（Metrics / Logs 证据）

1. Grafana：Chat P99 / Error Rate 是否升高？
2. 分段延迟：Java `chat.stream.end` vs Python `chat.stream.end`（`ragMs` / `llmTtfbMs` / `mcpMs`）
3. 资源：JVM heap、HikariCP、Kafka publish failures
4. 日志检索：`traceId="<id>"` 跨 control-plane / ai-plane

## 为何未更早发现

- 缺告警？阈值不合理？Dashboard 未覆盖？

## 修复动作

- 临时缓解：
- 永久修复：

## 跟进项

- [ ] 告警规则
- [ ] 超时 / 熔断调整
- [ ] 文档 / Runbook 更新
