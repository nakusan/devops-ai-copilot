package com.devops.copilot.modules.file.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * Kafka topic 名称（与 Python Consumer 约定一致）。
 */
@ConfigurationProperties(prefix = "copilot.kafka")
public class KafkaTopicProperties {

    private final Topics topics = new Topics();

    public Topics getTopics() {
        return topics;
    }

    public static class Topics {
        private String knowledgeIngest = "knowledge.ingest.v1";
        private String analysisIngest = "analysis.ingest.v1";
        private String knowledgeDlq = "knowledge.ingest.dlq.v1";
        private String analysisDlq = "analysis.ingest.dlq.v1";

        public String getKnowledgeIngest() {
            return knowledgeIngest;
        }

        public void setKnowledgeIngest(String knowledgeIngest) {
            this.knowledgeIngest = knowledgeIngest;
        }

        public String getAnalysisIngest() {
            return analysisIngest;
        }

        public void setAnalysisIngest(String analysisIngest) {
            this.analysisIngest = analysisIngest;
        }

        public String getKnowledgeDlq() {
            return knowledgeDlq;
        }

        public void setKnowledgeDlq(String knowledgeDlq) {
            this.knowledgeDlq = knowledgeDlq;
        }

        public String getAnalysisDlq() {
            return analysisDlq;
        }

        public void setAnalysisDlq(String analysisDlq) {
            this.analysisDlq = analysisDlq;
        }
    }
}
