package com.devops.copilot.modules.conversation.logging;

/**
 * 聊天链路统一日志格式，便于 docker logs | grep '[CHAT]' 追踪。
 *
 * <p>约定：{@code [CHAT] step=序号.中文步骤名 key=value ...}，文本字段用 preview 截断。
 *
 * <p>Java 侧一轮成功对话固定 4 条 INFO，序号不与 Python 侧（10~15）重叠：
 * <ol>
 *   <li>{@code 01.接收} —— ChatController，全链路唯一打用户原文的地方</li>
 *   <li>{@code 03.准备} —— ChatService，user 消息落库 + Agent 配置 + 历史条数</li>
 *   <li>{@code 04.出站} —— AiPlaneClient，调 Python 前的唯一标记</li>
 *   <li>{@code 08.结束} —— ChatService，status/durationMs/tokenEvents/usageTotal/quotaAfter</li>
 * </ol>
 *
 * <p>其余为分支路径，正常不出现：{@code 03.幂等回放}、{@code 04.出站失败}、
 * {@code 08.SSE超时}、{@code 08.取消}、{@code 08.结束 status=error|upstream_fail|persist_fail}。
 *
 * <p>逐 token / 逐 citation / done payload 一律不打：明细由 Python 侧结构化日志承载，
 * 条数汇总进 {@code 08.结束}。新增日志前先确认字段没有在上述四条里出现过。
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
