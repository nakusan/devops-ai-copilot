package com.devops.copilot.modules.security.filter;

import org.junit.jupiter.api.Test;

import java.util.Optional;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

class TraceIdFilterTest {

    @Test
    void extractsTraceIdFromValidTraceparent() {
        Optional<String> id = TraceIdFilter.extractFromTraceparent(
                "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01");
        assertTrue(id.isPresent());
        assertEquals("4bf92f3577b34da6a3ce929d0e0e4736", id.get());
    }

    @Test
    void rejectsMalformedTraceparent() {
        assertTrue(TraceIdFilter.extractFromTraceparent(null).isEmpty());
        assertTrue(TraceIdFilter.extractFromTraceparent("not-a-traceparent").isEmpty());
        assertTrue(TraceIdFilter.extractFromTraceparent("00-short-00f067aa0ba902b7-01").isEmpty());
    }
}
