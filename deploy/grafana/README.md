# Grafana（Phase 5 / W10）

- Datasource：`datasources/prometheus.yml` → `http://prometheus:9090`
- Dashboard provisioning：`dashboards/provider.yml`
- Dashboard JSON：`dashboard-json/overview.json`（Chat QPS/P99、Error、RAG/LLM/MCP、JVM）

本地访问：http://localhost:3000 （admin / admin）

应用需在宿主机监听 8080/8000，Prometheus 经 `host.docker.internal` 抓取。
