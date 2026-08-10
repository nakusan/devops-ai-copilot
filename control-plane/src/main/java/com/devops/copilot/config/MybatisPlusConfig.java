package com.devops.copilot.config;

import com.baomidou.mybatisplus.annotation.DbType;
import com.baomidou.mybatisplus.autoconfigure.ConfigurationCustomizer;
import com.baomidou.mybatisplus.extension.plugins.MybatisPlusInterceptor;
import com.baomidou.mybatisplus.extension.plugins.inner.PaginationInnerInterceptor;
import com.devops.copilot.common.mybatis.UuidTypeHandler;
import org.mybatis.spring.annotation.MapperScan;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.UUID;

/**
 * MyBatis Plus 全局配置：分页插件 + Mapper 扫描 + UUID TypeHandler。
 */
@Configuration
@MapperScan({
        "com.devops.copilot.modules.security.mapper",
        "com.devops.copilot.modules.conversation.mapper",
        "com.devops.copilot.modules.file.mapper"
})
public class MybatisPlusConfig {

    @Bean
    public MybatisPlusInterceptor mybatisPlusInterceptor() {
        MybatisPlusInterceptor interceptor = new MybatisPlusInterceptor();
        // 分页必须加插件，否则 selectPage 不会改写 SQL
        interceptor.addInnerInterceptor(new PaginationInnerInterceptor(DbType.POSTGRE_SQL));
        return interceptor;
    }

    /**
     * 显式注册 UUID TypeHandler，确保 MP 构建 autoResultMap 时能解析 id 等 UUID 字段。
     * （仅靠 type-handlers-package 扫描在部分版本/时机下仍可能漏注册，故双保险。）
     */
    @Bean
    public ConfigurationCustomizer uuidTypeHandlerCustomizer() {
        return configuration -> configuration.getTypeHandlerRegistry()
                .register(UUID.class, UuidTypeHandler.class);
    }
}
