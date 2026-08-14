package com.devops.copilot.modules.file.logging;

/**
 * 异步文件链路（知识库 / 分析）统一日志格式。
 *
 * <p>约定：{@code [INGEST] step=序号.步骤名 kind=knowledge|analysis key=value ...}，
 * 便于 {@code docker logs | grep '\[INGEST\]'} 追踪。
 *
 * <p>Java 侧一次上传固定 3 条 INFO（Python worker 用 11~17）：
 * <ol>
 *   <li>{@code 01.recv} —— Controller，唯一打 filename/sizeBytes 的地方</li>
 *   <li>{@code 05.stored} —— Service，objectKey/ext/mimeType/sizeBytes/status=PENDING</li>
 *   <li>{@code 06.kafka_ok} —— Producer，topic/offset/jobId</li>
 * </ol>
 *
 * <p>Python 回调状态时再加 {@code 16.status}（{@code 旧→新}，FAILED 升 WARN）。
 * 分支路径：{@code 02.rate_limit status=exceeded}、{@code 04.minio_fail}、
 * {@code 06.kafka_fail}、{@code 08.failed}。
 *
 * <p>正文不要再写 {@code traceId=}，logback pattern 已带 {@code [traceId=%X{traceId}]}。
 */
public final class IngestFlowLog {

    public static final String PREFIX = "[INGEST]";
    private static final int PREVIEW_MAX = 120;

    private IngestFlowLog() {
    }

    public static String preview(String text) {
        if (text == null) {
            return "";
        }
        String oneLine = text.replace('\n', ' ').replace('\r', ' ').trim();
        if (oneLine.length() <= PREVIEW_MAX) {
            return oneLine;
        }
        return oneLine.substring(0, PREVIEW_MAX) + "…";
    }

    public static String msg(String kind, String step, String details) {
        return PREFIX + " step=" + step + " kind=" + kind + " " + details;
    }
}
