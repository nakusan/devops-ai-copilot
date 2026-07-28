package com.devops.copilot.modules.conversation.controller.dto;

import java.util.List;

/** 简单分页包装（MVP）。 */
public record PageResponse<T>(
        List<T> items,
        long total,
        long page,
        long size
) {
}
