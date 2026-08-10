# 多阶段构建：Maven 编译 → 精简 JRE 运行时（Phase 6 / W12）
#
# 为何多阶段：
# - build 阶段需要完整 JDK + Maven 依赖缓存，体积大
# - runtime 只需 JRE + fat jar，缩小攻击面与镜像体积
# 注：不写 # syntax=docker/dockerfile:1，避免构建时强制拉取
# docker.io/docker/dockerfile（国内/受限网络常超时）。

# ---------- build ----------
FROM maven:3.9.9-eclipse-temurin-21 AS build
WORKDIR /build

# 先只拷 POM，利用 Docker 层缓存加速依赖下载
COPY pom.xml .
RUN mvn -B -q -DskipTests dependency:go-offline

COPY src ./src
# 打 Spring Boot fat jar；测试交给 CI，镜像构建跳过以加快交付
RUN mvn -B -DskipTests package \
    && cp target/control-plane-*.jar /build/app.jar

# ---------- runtime ----------
FROM eclipse-temurin:21-jre-jammy AS runtime

# curl：Compose healthcheck 探活 /actuator/health
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 非 root 运行（业界容器安全基线）
RUN groupadd --system app && useradd --system --gid app --home /app app
WORKDIR /app

COPY --from=build /build/app.jar /app/app.jar
USER app

EXPOSE 8080

# 容器内 JVM：尊重容器内存限制（Java 21 默认已较好，显式留扩展点）
ENV JAVA_OPTS=""

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8080/actuator/health || exit 1

ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /app/app.jar"]
