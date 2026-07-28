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
