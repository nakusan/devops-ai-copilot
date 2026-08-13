package com.devops.copilot.modules.conversation.config;

import io.netty.channel.ChannelOption;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.client.reactive.ReactorClientHttpConnector;
import org.springframework.web.reactive.function.client.WebClient;
import reactor.netty.http.client.HttpClient;

/**
 * WebClient 专用于调用 AI Plane。
 *
 * <p>应用仍是 Servlet MVC；引入 webflux 仅为非阻塞读 NDJSON 流，避免长时间占用 Tomcat 工作线程。
 *
 * <p><b>必须使用注入的 {@link WebClient.Builder}</b>：Spring Boot 会挂上
 * ObservationWebClientCustomizer，自动注入 W3C traceparent（设计 6.10 §6.5）。
 * 若改成 {@code WebClient.create()}，链路传播会静默失效。
 */
@Configuration
@EnableConfigurationProperties({AiPlaneProperties.class, ChatProperties.class})
public class AiPlaneClientConfig {

    @Bean
    public WebClient aiPlaneWebClient(AiPlaneProperties properties, WebClient.Builder builder) {
        HttpClient httpClient = HttpClient.create()
                .option(ChannelOption.CONNECT_TIMEOUT_MILLIS, (int) properties.getConnectTimeout().toMillis())
                .responseTimeout(properties.getReadTimeout());

        return builder
                .baseUrl(properties.getBaseUrl())
                .clientConnector(new ReactorClientHttpConnector(httpClient))
                .build();
    }
}
