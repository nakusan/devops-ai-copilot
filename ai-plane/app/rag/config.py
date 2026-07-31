"""RAG 模块配置说明（实际值集中在 app.config.Settings）。"""

# 切块 / Embedding / Kafka topic 等均通过环境变量注入 Settings，
# 避免与根配置双源漂移。
