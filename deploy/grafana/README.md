# Grafana（Phase 5 / W10 + Phase 7 / P1）

- Datasource：`datasources/prometheus.yml` → `http://prometheus:9090`
- Datasource：`datasources/tempo.yml` → `http://tempo:3200`（链路追踪；宿主机访问：`localhost:23200`）
- Dashboard provisioning：`dashboards/provider.yml`
- Dashboard JSON：`dashboard-json/overview.json`（Chat QPS/P99、Error、RAG/LLM/MCP、JVM）

本地访问：http://localhost:23000 （admin / admin）

Compose 全栈（`make stack-up`）时 Prometheus 按服务名抓取；应用在宿主机跑时叠用
`docker-compose.hybrid-metrics.yml`。Tempo 接受 OTLP：`http://tempo:4318/v1/traces`。
