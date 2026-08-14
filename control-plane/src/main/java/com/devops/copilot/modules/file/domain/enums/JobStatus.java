package com.devops.copilot.modules.file.domain.enums;

/**
 * 任务状态机：PENDING → PROCESSING → COMPLETED | FAILED。
 */
public enum JobStatus {
    PENDING,
    PROCESSING,
    COMPLETED,
    FAILED;

    /**
     * 是否已到终态（Kafka worker 不会再回调）。
     *
     * <p>删除文件前用它把 PENDING/PROCESSING 挡掉，避免删掉行之后 worker 的状态回调撞 404。
     *
     * @param status 库里存的状态字符串；null 或非法值一律视为非终态，倾向保守拒绝
     */
    public static boolean isTerminal(String status) {
        return COMPLETED.name().equals(status) || FAILED.name().equals(status);
    }
}
