.PHONY: help infra-up infra-down infra-ps stack-up stack-down stack-ps \
	java-compile java-test python-sync python-lint python-typecheck python-test \
	python-worker ci-local

COMPOSE := docker compose -f deploy/docker-compose.yml

help:
	@echo "可用目标："
	@echo "  infra-up       启动中间件（postgres/redis/kafka/minio/prometheus/grafana）"
	@echo "  infra-down     停止中间件"
	@echo "  infra-ps       查看中间件容器状态"
	@echo "  stack-up       全栈启动（中间件 + control-plane + ai-plane + worker）"
	@echo "  stack-down     停止全栈"
	@echo "  stack-ps       查看全栈容器状态"
	@echo "  java-compile   编译 control-plane（跳过测试）"
	@echo "  java-test      运行 control-plane 单元测试"
	@echo "  python-sync    同步 ai-plane 依赖（uv sync）"
	@echo "  python-lint    对 ai-plane 执行 ruff check"
	@echo "  python-typecheck  对 ai-plane 执行 pyright"
	@echo "  python-test    运行 ai-plane pytest"
	@echo "  python-worker  启动独立 Kafka Worker（需 KAFKA_BOOTSTRAP）"
	@echo "  ci-local       本地执行与 CI 等价的检查（不含 Docker build）"

infra-up:
	$(COMPOSE) up -d

infra-down:
	$(COMPOSE) down

infra-ps:
	$(COMPOSE) ps

# profile=apps 拉起双栈应用；--build 确保 Dockerfile 变更生效
stack-up:
	$(COMPOSE) --profile apps up -d --build

stack-down:
	$(COMPOSE) --profile apps down

stack-ps:
	$(COMPOSE) --profile apps ps

java-compile:
	cd control-plane && mvn -q -DskipTests compile

java-test:
	cd control-plane && mvn -q test

python-sync:
	cd ai-plane && uv sync --extra dev

python-lint:
	cd ai-plane && uv run ruff check .

python-typecheck:
	cd ai-plane && uv run pyright app

python-test:
	cd ai-plane && uv run pytest -q

python-worker:
	cd ai-plane && uv run python -m app.worker

ci-local: java-test python-sync python-lint python-typecheck python-test
