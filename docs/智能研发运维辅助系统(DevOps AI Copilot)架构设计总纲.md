# 智能研发运维辅助系统 (DevOps AI Copilot) 架构设计总纲

---

## 1. 项目背景与建设目标 (Project Background & Objectives)

### 1.1 业务背景

当前企业内部研发排查线上故障（如 OOM、接口超时）时，面临数据孤岛问题：需跨越知识库（Wiki）、日志系统（Kibana/本地堆栈）、监控大盘（Grafana）与数据库。排查链路长，且对新员工门槛极高。通用大语言模型缺乏企业私有上下文与操作权限，直接提问易产生“幻觉”。

### 1.2 工程训练目标

本项目旨在通过构建一个垂直领域的 AI 平台后台，跳出传统的表单驱动 (Form-driven) CRUD 模式，完成向事件驱动 (Event-driven)、流式交互 (Streaming) 与跨语言微服务协同的工程能力跃迁。重点攻克分布式可观测性、大文件异步处理与高并发限流。

---

## 2. 核心使用场景 (Core Scenarios)

* **场景一：基于 RAG 的私有知识排查**
* *动作*：用户提问“今日早盘商品服务报 STATUS_899 错误是什么原因？”
* *系统行为*：拦截请求校验研发组限额，触发检索增强生成 (Retrieval-Augmented Generation, RAG)，从向量数据库中召回内部《状态码字典》与《历史故障复盘报告》，组装上下文并流式输出结论。


* **场景二：长耗时大文件异步分析**
* *动作*：用户上传一份 50MB 的 Java Heap Dump 日志文件。
* *系统行为*：网关层极速响应接收状态，文件转存对象存储。消息队列触发后台 Python 节点离线解析文件特征，完成后通知前端，避免阻塞应用服务器主线程。


* **场景三：基于 MCP 的实时监控数据获取**
* *动作*：用户要求分析“当前数据库连接数是否异常”。
* *系统行为*：Agent 通过模型上下文协议 (Model Context Protocol, MCP) 客户端，安全调用企业内网的 Prometheus 接口或执行只读 SQL 查询，基于实时数值生成诊断报告。



---

## 3. 系统总体架构 (System Architecture)

系统采用 **控制面 (Control Plane) + 智能面 (AI Plane)** 的跨语言双栈基座架构。

### 3.1 控制面：Java 层 (Spring Boot 3.x)

* **定位**：系统网关与业务操作系统。
* **核心职责**：
* 统一接入与鉴权（基于 JWT）。
* API 速率限制与防刷（基于 Redis Lua 脚本）。
* 用户、会话元数据管理（MyBatis Plus + PostgreSQL）。
* 维持 Server-Sent Events (SSE) 长连接。
* 大文件接收与事件分发。



### 3.2 智能面：Python 层 (FastAPI)

* **定位**：AI 编排与计算大脑。
* **核心职责**：
* ReAct 工具循环（LLM function calling）：模型决定检索 / MCP / 分析任务调用，编排器执行并回灌，最终流式回答。
* RAG 数据管道（文档解析、切块分发、向量化计算）。
* 外部工具与系统挂载（MCP Client）。
* 对接兼容 OpenAI 标准的模型 API（如 DeepSeek/Qwen）。



### 3.3 基础设施与可观测性底座 (Infrastructure)

* **持久化**：PostgreSQL（关系型数据）+ `pgvector` 插件（高维向量数据）。
* **消息总线**：Kafka（解耦长耗时文件解析与向量化任务）。
* **对象存储**：MinIO（存储原始日志文件、PDF 文档）。
* **全链路追踪**：OpenTelemetry（生成全局 Trace ID，串联 Java、Python、Redis、Kafka 调用）。
* **指标监控**：Prometheus 抓取 Actuator 指标，Grafana 可视化面板。

---

## 4. 核心架构流转图 (Core Data Flows)

### 4.1 同步流式诊断链路 (Synchronous Streaming Flow)

1. **鉴权与追踪**：客户端发起源请求，Java 层完成 JWT 校验，生成全局 `Trace ID` 并将数据写入 MDC (Mapped Diagnostic Context)。
2. **限流拦截**：调用 Redis 校验该用户的 Token 消耗额度与调用频率。
3. **跨语言 RPC**：Java 端基于 `WebClient` 将携带 `Trace ID` 与 `Session ID` 的请求转发至 Python 端 FastAPI。
4. **状态机激活**：Python 端 LangGraph 以 Java 传入的 `history` 初始化会话上下文（**PG 为唯一真相源**，MVP 不用 Redis checkpoint）。
5. **图节点流转**：Router 判定意图；可进入 `RetrieveNode`、`ToolNode`、**并行 FanOutNode（RAG∥MCP）** 或 `AnalysisLookupNode`。
6. **流式级联透传**：LLM 流式响应抵达 Python（**NDJSON**）→ Java 解析并转为 **SSE** 推给客户端。

### 4.2 异步知识入库链路 (Asynchronous Ingestion Flow)

1. **文件转存**：Java 端接收用户上传的历史复盘 PDF 或大日志文件，流式写入 MinIO，返回预签名 URL (Presigned URL)。
2. **事件发布**：Java 端在 PostgreSQL 插入 `status=PENDING` 的记录，向 Kafka topic `knowledge.ingest.v1` 发送消息。前端收到 HTTP 202 响应。
3. **离线消费**：Python 消费者拉取 Kafka 消息，将 DB 状态更新为 `PROCESSING`。
4. **向量化处理**：Python 下载 MinIO 文件进行语义分块 (Semantic Chunking)，批量请求 Embedding 模型，将结果存入 `pgvector`。
5. **状态终结**：写入完成，更新 DB 状态为 `COMPLETED`。

---

## 5. 功能模块划分 (Functional Module Breakdown)

| 模块分类 | 模块名称 | 承载技术 | 核心功能点描述 |
| --- | --- | --- | --- |
| **基础基建** | **网关与安全模块** | Java/Redis | JWT 生成与续签；基于 Redis 的单 IP 防抖与令牌桶限流。 |
| **业务管控** | **会话与元数据模块** | Java/PostgreSQL | 会话 (Session) 树状结构存储；Agent 参数字典配置CRUD。 |
| **异步流转** | **文件与调度模块** | Java/Kafka/MinIO | 大文件的断点续传/预签名直传；Kafka 生产者确认与消费者死信队列 (DLQ) 机制。 |
| **AI 计算** | **知识检索模块 (RAG)** | Python/pgvector | 文档清洗解析；Token 切块算法；高维向量余弦相似度搜索。 |
| **AI 计算** | **大文件分析模块** | Python/Kafka | 消费 `analysis.ingest.v1`；MVP 关键字解析；更新 `analysis_jobs`。 |
| **AI 计算** | **智能体编排模块** | Python/ReAct | LLM function calling 多轮工具；RAG/MCP/分析由模型选路；对话上下文以 PG 为准 |
| **外部通信** | **工具挂载模块 (MCP)** | Python/MCP | MCP 客户端实现，标准化对接外部只读数据库或监控 API 提供实时状态。 |
| **可观测性** | **遥测监控模块** | OTel/Prometheus | 跨越双栈的 HTTP 头 Trace ID 注入；JVM/Python GC 耗时及 API QPS 大盘展示。 |

---

## 6. 12周工程落地演进路线 (12-Week Execution Roadmap)

> 此路线图强制约束每周唯一核心目标，遵循“先基建后应用，先同步后异步”的原则。

### 阶段一：控制面基建构建 (Weeks 1-3)

* **Week 1**：搭建 Java 21 + Spring Boot 3 脚手架；完成 JWT 统一鉴权与全局异常接管体系。
* **Week 2**：集成 MyBatis Plus；配置 HikariCP 连接池参数；完成 User/Agent 基础表设计与 CRUD。
* **Week 3**：引入 Redis；实现基于 Lua 脚本的高并发 API 限流策略与防缓存击穿机制。

### 阶段二：跨语言通信与流式引擎 (Weeks 4-5)

* **Week 4**：搭建 Python FastAPI 基座；实现 Java 到 Python 的内网 HTTP RPC 调用与超时重试策略。
* **Week 5**：打通双栈流式通信；实现 Python 获取大模型结果，通过 Java 以 SSE 协议零阻塞推流至客户端。

### 阶段三：AI 工作流与私有知识整合 (Weeks 6-7)

* **Week 6**：Python 端引入 LangGraph；含 `rag_and_tool` 并行；`history` 不含本条；流式采用模式 A（图外 LLM）。
* **Week 7**：开通 PostgreSQL `pgvector` 扩展；跑通基于余弦距离 (`<=>`) 或内积 (`<#>`) 的基础 SQL 向量检索。

### 阶段四：异步削峰与系统级联 (Weeks 8-9)

* **Week 8**：引入 MinIO；实现 Java 端文件流式上传；**6.8 Analysis Worker** 简化解析（场景二骨架）。
* **Week 9**：引入 Kafka 集群；完成离线 RAG 数据清洗管道；Java 投递解析任务，Python 消费进行文档切块分发。

### 阶段五：可观测体系与工具挂载 (Weeks 10-11)

* **Week 10**：引入 OpenTelemetry 探针；实现跨越 HTTP、JDBC、Redis 与 Kafka 的统一分布式调用链分析。
* **Week 11**：Orchestrator ReAct + MCP Mock；LLM function calling 验证实时指标与知识检索多轮诊断。

### 阶段六：CI/CD 与容器化交付 (Week 12)

* **Week 12**：编写多阶段 `Dockerfile`；编写 `docker-compose.yml` 完成全套双栈微服务与 5 种中间件的本地一键编排启动。引入 GitHub Actions 跑通静态代码审查。