package com.devops.copilot.modules.file.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.kafka.clients.producer.ProducerConfig;
import org.apache.kafka.common.serialization.StringSerializer;
import org.springframework.boot.autoconfigure.kafka.KafkaProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.kafka.core.DefaultKafkaProducerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.core.ProducerFactory;
import org.springframework.kafka.support.serializer.JsonSerializer;

import java.util.HashMap;
import java.util.Map;

/**
 * Kafka Producer：复用 Spring Boot 的 ObjectMapper（含 JavaTimeModule），
 * 保证 OffsetDateTime 以 ISO-8601 写出，Python 可解析。
 */
@Configuration
public class KafkaProducerConfig {

    @Bean
    public ProducerFactory<String, Object> ingestProducerFactory(
            KafkaProperties kafkaProperties, ObjectMapper objectMapper) {
        Map<String, Object> props = new HashMap<>(kafkaProperties.buildProducerProperties(null));
        // 序列化器实例由 factory 注入；剥离 YAML 中的 serializer 类名，避免与 setValueSerializer 冲突
        props.remove(ProducerConfig.KEY_SERIALIZER_CLASS_CONFIG);
        props.remove(ProducerConfig.VALUE_SERIALIZER_CLASS_CONFIG);
        props.keySet().removeIf(k -> k.toString().startsWith("spring.json."));
        // 仅通过 configure(properties) 关闭类型头；不可再调用 setAddTypeInfo（会与 configure 互斥）
        props.put(JsonSerializer.ADD_TYPE_INFO_HEADERS, false);

        JsonSerializer<Object> valueSerializer = new JsonSerializer<>(objectMapper);

        DefaultKafkaProducerFactory<String, Object> factory =
                new DefaultKafkaProducerFactory<>(props);
        factory.setKeySerializer(new StringSerializer());
        factory.setValueSerializer(valueSerializer);
        return factory;
    }

    @Bean
    public KafkaTemplate<String, Object> kafkaTemplate(
            ProducerFactory<String, Object> ingestProducerFactory) {
        return new KafkaTemplate<>(ingestProducerFactory);
    }
}
