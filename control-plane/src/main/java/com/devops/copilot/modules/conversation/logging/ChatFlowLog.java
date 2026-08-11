package com.devops.copilot.modules.conversation.logging;

/**
 * 聊天链路统一日志格式，便于 docker logs | grep '[CHAT]' 追踪。
 *
 * <p>约定：{@code [CHAT] step=序号.中文步骤名 key=value ...}，文本字段用 preview 截断。
 */
public final class ChatFlowLog {

    public static final String PREFIX = "[CHAT]";
    private static final int PREVIEW_MAX = 120;

    private ChatFlowLog() {
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

    public static String msg(String step, String details) {
        return PREFIX + " step=" + step + " " + details;
    }
}
