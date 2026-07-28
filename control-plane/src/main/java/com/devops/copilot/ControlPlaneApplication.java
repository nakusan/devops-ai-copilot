package com.devops.copilot;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.transaction.annotation.EnableTransactionManagement;

/**
 * 控制面启动入口（对外唯一公网 API 网关）。
 *
 * <p>Phase 1：JWT 鉴权、Agent/Session CRUD、限流与配额服务。
 */
@SpringBootApplication
@EnableTransactionManagement
public class ControlPlaneApplication {

    public static void main(String[] args) {
        SpringApplication.run(ControlPlaneApplication.class, args);
    }
}
