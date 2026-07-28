.PHONY: help infra-up infra-down infra-ps java-compile python-sync python-lint ci-local

COMPOSE := docker compose -f deploy/docker-compose.yml

help:
	@echo "可用目标："
	@echo "  infra-up       启动中间件（postgres/redis/kafka/minio）"
	@echo "  infra-down     停止中间件"
	@echo "  infra-ps       查看中间件容器状态"
	@echo "  java-compile   编译 control-plane（跳过测试）"
	@echo "  python-sync    同步 ai-plane 依赖（uv sync）"
	@echo "  python-lint    对 ai-plane 执行 ruff check"
	@echo "  ci-local       本地执行与 CI 等价的检查"

infra-up:
	$(COMPOSE) up -d

infra-down:
	$(COMPOSE) down

infra-ps:
	$(COMPOSE) ps

java-compile:
	cd control-plane && mvn -q -DskipTests compile

python-sync:
	cd ai-plane && uv sync

python-lint:
	cd ai-plane && uv run ruff check .

ci-local: java-compile python-sync python-lint
