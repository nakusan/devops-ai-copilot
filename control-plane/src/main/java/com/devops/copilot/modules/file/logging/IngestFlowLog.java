package com.devops.copilot.modules.file.logging;

/**
 * 异步文件链路（知识库 / 分析）统一日志格式。
 *
 * <p>约定：{@code [INGEST] step=序号.步骤名 kind=knowledge|analysis key=value ...}，
 * 便于 {@code docker logs | grep '\[INGEST\]'} 追踪。
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
