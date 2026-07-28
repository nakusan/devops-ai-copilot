package com.devops.copilot.modules.security.ratelimit;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 限流阈值配置。capacity 近似「每分钟请求数」，与 Lua 桶容量一致。
 */
@ConfigurationProperties(prefix = "copilot.rate-limit")
public class RateLimitProperties {

    private int userPerMinute = 60;
    private int ipPerMinute = 120;

    public int getUserPerMinute() {
        return userPerMinute;
    }

    public void setUserPerMinute(int userPerMinute) {
        this.userPerMinute = userPerMinute;
    }

    public int getIpPerMinute() {
        return ipPerMinute;
    }

    public void setIpPerMinute(int ipPerMinute) {
        this.ipPerMinute = ipPerMinute;
    }
}
