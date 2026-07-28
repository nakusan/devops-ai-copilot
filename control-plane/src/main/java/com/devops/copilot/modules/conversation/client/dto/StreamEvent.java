package com.devops.copilot.modules.conversation.client.dto;

import com.fasterxml.jackson.databind.JsonNode;

/**
 * Python → Java NDJSON 行事件。
 */
public class StreamEvent {

    private String type;
    private String text;
    private JsonNode data;
    private JsonNode done;
    private JsonNode error;

    public String getType() {
        return type;
    }

    public void setType(String type) {
        this.type = type;
    }

    public String getText() {
        return text;
    }

    public void setText(String text) {
        this.text = text;
    }

    public JsonNode getData() {
        return data;
    }

    public void setData(JsonNode data) {
        this.data = data;
    }

    public JsonNode getDone() {
        return done;
    }

    public void setDone(JsonNode done) {
        this.done = done;
    }

    public JsonNode getError() {
        return error;
    }

    public void setError(JsonNode error) {
        this.error = error;
    }
}
